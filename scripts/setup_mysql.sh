#!/bin/bash
# Configure MariaDB pour Open edX devstack local
# Compatible MariaDB (ubuntu noble = MariaDB 10.11 par défaut)

set -e

MYSQL_USER="openedx"
MYSQL_PASS="openedx_pass"

echo "==> Détection du serveur SQL..."
sudo mysql -e "SELECT VERSION();" 2>&1

echo ""
echo "==> Création de l'utilisateur '${MYSQL_USER}' et des bases..."

sudo mysql <<SQL
CREATE USER IF NOT EXISTS '${MYSQL_USER}'@'127.0.0.1' IDENTIFIED BY '${MYSQL_PASS}';
CREATE USER IF NOT EXISTS '${MYSQL_USER}'@'localhost'  IDENTIFIED BY '${MYSQL_PASS}';
GRANT ALL PRIVILEGES ON *.* TO '${MYSQL_USER}'@'127.0.0.1' WITH GRANT OPTION;
GRANT ALL PRIVILEGES ON *.* TO '${MYSQL_USER}'@'localhost'  WITH GRANT OPTION;
CREATE DATABASE IF NOT EXISTS openedx       CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS edxapp_csmh   CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
FLUSH PRIVILEGES;
SQL

echo ""
echo "==> Test de connexion avec le nouvel utilisateur..."
mysql -h 127.0.0.1 -u "${MYSQL_USER}" -p"${MYSQL_PASS}" -e "SHOW DATABASES;" 2>&1

echo ""
echo "==> Terminé. Bases créées : openedx, edxapp_csmh"
