# circ_toolbox_project/circ_toolbox/backend/init_db.sh
#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status

# Load environment variables using the process_env.sh script
circ_toolbox/backend/process_env.sh

echo "🔄 Checking PostgreSQL availability at $POSTGRES_HOST:$POSTGRES_PORT..."

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


# Wait for PostgreSQL to be ready
until PGPASSWORD=$POSTGRES_PASSWORD psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -c '\q' 2>/dev/null; do
  echo "⏳ Waiting for PostgreSQL to start..."
  sleep 10
done

echo "✅ PostgreSQL is up and running."

## Check if the database exists
#DB_EXISTS=$(PGPASSWORD=$POSTGRES_PASSWORD psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -tc "SELECT 1 FROM pg_database WHERE datname='$POSTGRES_DB'" | tr -d '[:space:]')
#
#if [[ "$DB_EXISTS" != "1" ]]; then
#    echo "🛠️  Creating database: $POSTGRES_DB..."
#    PGPASSWORD=$POSTGRES_PASSWORD psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -c "CREATE DATABASE $POSTGRES_DB;"
#else
#    echo "ℹ️ Database '$POSTGRES_DB' already exists."
#fi
#
## Run database schema initialization via Python (Step B)
#echo "🏗️ Running Python database initialization..."
## python /app/circ_toolbox/backend/scripts/init_db.py
#
#echo "✅ Database setup completed successfully."
#
#
#

# # to run:
# chmod +x init_db.sh
# ./init_db.sh


# bash circ_toolbox/backend/scripts/init_db.sh
