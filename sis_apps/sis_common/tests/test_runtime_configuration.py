import json
from importlib.metadata import version
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import CommandError
from packaging.requirements import Requirement

from scripts.sisctl import configure, read_configuration
from sis_common.bootstrap import BootstrapInstitutionCommand
from sis_common.config import (
    get_database_configuration,
    get_lms_configuration,
    get_sis_mode,
    get_variant_environment,
    load_environment,
)


def test_environment_precedence(tmp_path, monkeypatch):
    variant = tmp_path / "sis_secondaire"
    variant.mkdir()
    (tmp_path / ".env").write_text("SIS_TEST_VALUE=shared\nSIS_TEST_SHARED=loaded\n")
    (variant / ".env").write_text("SIS_TEST_VALUE=variant\n")
    monkeypatch.delenv("SIS_TEST_VALUE", raising=False)
    monkeypatch.delenv("SIS_TEST_SHARED", raising=False)
    load_environment(variant)
    assert get_variant_environment("SIS_TEST_VALUE", "secondaire") == "variant"
    assert get_variant_environment("SIS_TEST_SHARED", "secondaire") == "loaded"
    monkeypatch.setenv("SIS_TEST_VALUE", "process")
    load_environment(variant)
    assert get_variant_environment("SIS_TEST_VALUE", "secondaire") == "process"
    monkeypatch.delenv("SIS_TEST_VALUE")
    monkeypatch.delenv("SIS_TEST_SHARED")


def test_variant_database_credentials_override_generic_values(monkeypatch):
    monkeypatch.setenv("DB_NAME", "shared")
    monkeypatch.setenv("DB_PASSWORD", "generic-password")
    monkeypatch.setenv("DB_NAME_SECONDAIRE", "secondary")
    monkeypatch.setenv("DB_PASSWORD_SECONDAIRE", "secondary-password")
    monkeypatch.delenv("DB_NAME_SUPERIEUR", raising=False)
    monkeypatch.delenv("DB_PASSWORD_SUPERIEUR", raising=False)
    assert get_database_configuration("secondaire")["NAME"] == "secondary"
    assert get_database_configuration("secondaire")["PASSWORD"] == "secondary-password"
    assert get_database_configuration("superieur")["PASSWORD"] == "generic-password"


def test_invalid_mode_fails_explicitly(monkeypatch):
    monkeypatch.setenv("SIS_MODE", "secondary")
    with pytest.raises(ImproperlyConfigured, match="SIS_MODE"):
        get_sis_mode("secondaire")


def test_missing_production_database_password_is_rejected(monkeypatch):
    monkeypatch.delenv("DB_PASSWORD", raising=False)
    monkeypatch.delenv("DB_PASSWORD_SECONDAIRE", raising=False)
    monkeypatch.setattr("sis_common.config.is_test_environment", lambda: False)
    with pytest.raises(ImproperlyConfigured, match="DB_PASSWORD_SECONDAIRE"):
        get_database_configuration("secondaire")


def test_standalone_local_authentication_needs_no_lms_configuration(monkeypatch):
    with patch.dict("os.environ", {"SIS_AUTH_MODE": "local"}, clear=True):
        monkeypatch.setattr("sis_common.config.is_test_environment", lambda: False)
        for variant in ("secondaire", "superieur"):
            configuration = get_lms_configuration(variant)
            assert configuration.pop("SIS_AUTH_MODE") == "local"
            assert all(value == "" for value in configuration.values())


def test_lms_authentication_still_requires_real_credentials(monkeypatch):
    with patch.dict("os.environ", {"SIS_AUTH_MODE": "lms"}, clear=True):
        monkeypatch.setattr("sis_common.config.is_test_environment", lambda: False)
        with pytest.raises(ImproperlyConfigured, match="EDX_OAUTH_CLIENT_ID"):
            get_lms_configuration("secondaire")
    with patch.dict("os.environ", {"SIS_AUTH_MODE": "unknown"}, clear=True):
        with pytest.raises(ImproperlyConfigured, match="SIS_AUTH_MODE"):
            get_lms_configuration("superieur")


def test_local_authentication_preserves_explicit_lms_integration(monkeypatch):
    values = {
        "SIS_AUTH_MODE": "local",
        "EDX_LMS_URL": "https://lms.example",
        "EDX_CMS_URL": "https://studio.example",
        "EDX_OAUTH_CLIENT_ID": "service",
        "EDX_OAUTH_CLIENT_SECRET": "configured-secret",
    }
    with patch.dict("os.environ", values, clear=True):
        configuration = get_lms_configuration("secondaire")
    assert all(configuration[key] == value for key, value in values.items())
    assert configuration["EDX_JWT_PUBLIC_SIGNING_JWK_SET"] == ""


def test_bootstrap_reads_private_configuration_from_stdin_without_consuming_the_password():
    command = BootstrapInstitutionCommand()
    options = vars(command.create_parser("manage.py", "bootstrap_institution").parse_args(["--config-stdin"]))
    source = StringIO('{"schema_name":"public"}\npassword-for-the-next-step\n')
    with patch("sys.stdin", source), pytest.raises(CommandError, match="non-public"):
        command.handle(**options)
    assert source.readline() == "password-for-the-next-step\n"


def test_locked_runtime_satisfies_both_dependency_manifests():
    root = Path(__file__).resolve().parents[2]
    for variant in ("secondaire", "superieur"):
        for line in (root / f"sis_{variant}/requirements/base.txt").read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                requirement = Requirement(line)
                assert version(requirement.name) in requirement.specifier, f"{variant}: {requirement}"


@pytest.mark.parametrize("secret", ["a'quote", "$VARIABLE", "two\nlines"])
def test_installer_rejects_ambiguous_secrets_without_creating_configuration(tmp_path, secret):
    jwks = tmp_path / "jwks.json"
    jwks.write_text(json.dumps({"keys": [{"kty": "RSA", "n": "test", "e": "AQAB"}]}))
    options = SimpleNamespace(
        env_file=tmp_path / ".env",
        domain="school.example",
        local=False,
        mode="dual",
        auth_mode="local",
        lms_url="https://lms.school.example",
        cms_url="https://studio.school.example",
        jwks=jwks,
        oauth_client_id="sis",
        issuer=None,
        audience="openedx",
    )
    with patch("getpass.getpass", return_value=secret), pytest.raises(ValueError):
        configure(options)
    assert not options.env_file.exists()


def test_installer_configuration_roundtrip_and_no_overwrite(tmp_path):
    jwks = tmp_path / "jwks.json"
    jwks.write_text(json.dumps({"keys": [{"kty": "RSA", "n": "test", "e": "AQAB"}]}))
    options = SimpleNamespace(
        env_file=tmp_path / ".env",
        domain="school.example",
        local=False,
        mode="dual",
        auth_mode="local",
        lms_url="https://lms.school.example",
        cms_url="https://studio.school.example",
        jwks=jwks,
        oauth_client_id="sis",
        issuer=None,
        audience="openedx",
    )
    with patch("getpass.getpass", return_value="installation-secret"):
        configure(options)
        original = options.env_file.read_bytes()
        with pytest.raises(ValueError, match="already exists"):
            configure(options)
    assert options.env_file.read_bytes() == original
    assert options.env_file.stat().st_mode & 0o777 == 0o600
    assert read_configuration(options.env_file)["EDX_OAUTH_CLIENT_SECRET"] == "installation-secret"
