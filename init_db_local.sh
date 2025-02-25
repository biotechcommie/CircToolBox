#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status

# Activate the Conda environment
source ~/miniconda3/bin/activate circrna_pipeline_env_p3_10

# Set the PYTHONPATH to the project root (circ_toolbox_project)
export PYTHONPATH=$(pwd)
echo "PYTHONPATH set to: $PYTHONPATH"

# Load environment variables from .env file safely, ignoring comments and empty lines
while IFS='=' read -r key value; do
  if [[ ! $key =~ ^# && -n $key ]]; then
    export "$key"="$value"
  fi
done < .env

echo "✅ Environment variables loaded successfully."

# Ensure PGDATA_DIR is set
if [ -z "$PGDATA_DIR" ]; then
    echo "❌ PGDATA_DIR is not set. Please add it to your .env file."
    exit 1
fi

# Ensure PostgreSQL data directory exists and initialize it if necessary
if [ ! -d "$PGDATA_DIR" ]; then
    echo "🛠️  PostgreSQL data directory not found at '$PGDATA_DIR'. Initializing new database cluster..."
    initdb -D "$PGDATA_DIR" -U "$POSTGRES_SUPERUSER" -A md5 --pwfile=<(echo "$POSTGRES_SUPERPASS") || { 
        echo "❌ Failed to initialize PostgreSQL database cluster. Check permissions."; 
        exit 1; 
    }
    echo "✅ PostgreSQL database cluster initialized successfully."

    # Configure PostgreSQL authentication for remote connections
    echo "host all all 0.0.0.0/0 md5" >> "$PGDATA_DIR/pg_hba.conf"
    echo "local all all trust" >> "$PGDATA_DIR/pg_hba.conf"
    echo "✅ PostgreSQL authentication configured."
else
    echo "ℹ️ PostgreSQL data directory found at '$PGDATA_DIR'."
fi

# Ensure PostgreSQL is stopped when the script exits
# trap 'pg_ctl -D "$PGDATA_DIR" stop > /dev/null 2>&1; echo "✅ PostgreSQL stopped."' EXIT

# Start PostgreSQL temporarily to create necessary roles
pg_ctl -D "$PGDATA_DIR" -o "-c listen_addresses='localhost'" -l logfile start
echo "⏳ Waiting for PostgreSQL to be available..."
sleep 5  # Give PostgreSQL time to start

# Create PostgreSQL Superuser (if not exists)
echo "🛠️  Ensuring PostgreSQL superuser '$POSTGRES_SUPERUSER' exists..."
PGPASSWORD=$POSTGRES_SUPERPASS psql -h localhost -p "$POSTGRES_PORT" -U "$POSTGRES_SUPERUSER" -tc "SELECT 1 FROM pg_roles WHERE rolname='$POSTGRES_SUPERUSER'" | tr -d '[:space:]' || \
PGPASSWORD=$POSTGRES_SUPERPASS psql -h localhost -p "$POSTGRES_PORT" -U "$POSTGRES_SUPERUSER" -c "CREATE ROLE $POSTGRES_SUPERUSER WITH SUPERUSER CREATEDB CREATEROLE LOGIN PASSWORD '$POSTGRES_SUPERPASS';"
echo "✅ PostgreSQL superuser '$POSTGRES_SUPERUSER' is ready."

# Ensure the application database exists before creating the application user
echo "🛠️  Checking if database '$POSTGRES_DB' exists..."
DB_EXISTS=$(PGPASSWORD=$POSTGRES_SUPERPASS psql -h "$POSTGRES_HOST" -U "$POSTGRES_SUPERUSER" -tc "SELECT 1 FROM pg_database WHERE datname='$POSTGRES_DB'" | tr -d '[:space:]')

if [[ "$DB_EXISTS" != "1" ]]; then
    echo "🛠️  Creating local database: $POSTGRES_DB..."
    PGPASSWORD=$POSTGRES_SUPERPASS psql -h "$POSTGRES_HOST" -U "$POSTGRES_SUPERUSER" -c "CREATE DATABASE $POSTGRES_DB OWNER $POSTGRES_SUPERUSER;"
    echo "✅ Database $POSTGRES_DB created successfully."
else
    echo "ℹ️ Database '$POSTGRES_DB' already exists."
fi

# Create Application User with Restricted Permissions (if not exists)
echo "🛠️  Ensuring application user '$POSTGRES_USER' exists..."

# First, check and create the user in the default 'postgres' database
USER_EXISTS=$(PGPASSWORD=$POSTGRES_SUPERPASS psql -h localhost -p "$POSTGRES_PORT" -U "$POSTGRES_SUPERUSER" -d postgres -tc "SELECT 1 FROM pg_roles WHERE rolname='$POSTGRES_USER'" | tr -d '[:space:]')

if [[ "$USER_EXISTS" != "1" ]]; then
    echo "🛠️  Creating application user '$POSTGRES_USER'..."
    PGPASSWORD=$POSTGRES_SUPERPASS psql -h localhost -p "$POSTGRES_PORT" -U "$POSTGRES_SUPERUSER" -d postgres -c "CREATE ROLE $POSTGRES_USER WITH LOGIN PASSWORD '$POSTGRES_PASSWORD';"
    echo "✅ PostgreSQL application user '$POSTGRES_USER' created."
else
    echo "ℹ️ Application user '$POSTGRES_USER' already exists."
fi

# Grant access to the application database after user creation
PGPASSWORD=$POSTGRES_SUPERPASS psql -h localhost -p "$POSTGRES_PORT" -U "$POSTGRES_SUPERUSER" -d postgres -c "GRANT CONNECT ON DATABASE $POSTGRES_DB TO $POSTGRES_USER;"
PGPASSWORD=$POSTGRES_SUPERPASS psql -h localhost -p "$POSTGRES_PORT" -U "$POSTGRES_SUPERUSER" -d postgres -c "GRANT ALL PRIVILEGES ON DATABASE $POSTGRES_DB TO $POSTGRES_USER;"

echo "✅ PostgreSQL application user '$POSTGRES_USER' now has access to the database."

# Grant privileges on schema to the application user
echo "🛠️  Granting privileges to application user '$POSTGRES_USER'..."
PGPASSWORD=$POSTGRES_SUPERPASS psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_SUPERUSER" -d "$POSTGRES_DB" <<EOF
GRANT USAGE, CREATE ON SCHEMA public TO $POSTGRES_USER;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO $POSTGRES_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO $POSTGRES_USER;
ALTER SCHEMA public OWNER TO $POSTGRES_USER;
EOF
echo "✅ Privileges granted to application user '$POSTGRES_USER'."

# Stop the temporary PostgreSQL server
pg_ctl -D "$PGDATA_DIR" stop > /dev/null 2>&1
echo "✅ PostgreSQL setup completed. Restarting in persistent mode."

# Start PostgreSQL persistently in the background
pg_ctl -D "$PGDATA_DIR" -o "-c listen_addresses='*'" -l logfile start
echo "✅ PostgreSQL server is running persistently."

# Verify PostgreSQL readiness
echo "🔄 Checking PostgreSQL availability at $POSTGRES_HOST:$POSTGRES_PORT..."

WAIT_LIMIT=30  # Limit wait time to 30 seconds
TRIES=0
until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER"; do
  ((TRIES++))
  if [[ $TRIES -eq $WAIT_LIMIT ]]; then
    echo "❌ PostgreSQL is not responding after $WAIT_LIMIT seconds. Exiting."
    exit 1
  fi
  echo "⏳ Waiting for PostgreSQL to start locally... Attempt $TRIES"
  sleep 1
done

echo "✅ PostgreSQL is up and running locally."

echo "✅ Local database setup completed successfully."

echo "🏁 Now you can start the application with:"
echo "   python circ_toolbox/main.py"





# chmod +x init_db_local.sh
#psql: error: connection to server at "localhost" (127.0.0.1), port 5432 failed: FATAL: role "postgres" does not exist


# Ensure PostgreSQL starts on boot
#if ! sudo systemctl is-enabled postgresql | grep -q "enabled"; then
#    echo "🔄 Enabling PostgreSQL to start on boot..."
#    sudo systemctl enable postgresql || { echo "❌ Failed to enable PostgreSQL auto-start."; exit 1; }
#    echo "✅ PostgreSQL is enabled to start on boot."
#fi
