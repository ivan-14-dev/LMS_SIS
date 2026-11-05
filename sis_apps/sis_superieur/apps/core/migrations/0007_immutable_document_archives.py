from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("core", "0006_documentarchive_archiverevocation_signatureapproval_and_more")]
    operations = [
        migrations.RunSQL(
            """
            CREATE FUNCTION sis_reject_archive_mutation() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'Les archives et leurs révocations sont immuables.';
            END;
            $$ LANGUAGE plpgsql;
            CREATE TRIGGER immutable_document_archive BEFORE UPDATE OR DELETE
                ON core_documentarchive FOR EACH ROW EXECUTE FUNCTION sis_reject_archive_mutation();
            CREATE TRIGGER immutable_archive_revocation BEFORE UPDATE OR DELETE
                ON core_archiverevocation FOR EACH ROW EXECUTE FUNCTION sis_reject_archive_mutation();
            """,
            """
            DROP TRIGGER immutable_archive_revocation ON core_archiverevocation;
            DROP TRIGGER immutable_document_archive ON core_documentarchive;
            DROP FUNCTION sis_reject_archive_mutation();
            """,
        )
    ]
