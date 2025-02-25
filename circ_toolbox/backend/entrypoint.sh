# circ_toolbox_project/circ_toolbox/backend/entrypoint.sh
#!/bin/bash

set -e  # Exit on error if any command fails

echo "Starting backend container..."

# Load Conda environment
source /opt/conda/etc/profile.d/conda.sh
conda activate circrna_pipeline_env || { echo "Failed to activate Conda environment"; exit 1; }

# Load environment variables from .env using process_env.sh script
/app/process_env.sh

# Ensure project root is added to PYTHONPATH if not already set
# export PYTHONPATH="${PYTHONPATH:-/app}"

# Debugging information
echo "Active Conda environment:"
conda info --envs
echo "Python path:"
which python
echo "Alembic path:"
which alembic
echo "PYTHONPATH: $PYTHONPATH"

# Navigate to the app directory inside the container
cd /app

# Check if migrations exist, and create if they don't
if [ ! -d "${DATABASE_DIR}/migrations/versions" ]; then
    echo "Initializing Alembic migrations for the first time..."
    alembic -c "${ALEMBIC_INI_PATH}" revision --autogenerate -m "initial migration"
    alembic -c "${ALEMBIC_INI_PATH}" upgrade head
else
    echo "Running Alembic migrations..."
    alembic -c "${ALEMBIC_INI_PATH}" upgrade head
fi

# Run initial data population script
echo "Populating initial data..."
python circ_toolbox/backend/initial_data.py || { echo "Initial data population failed"; exit 1; }

# Start the FastAPI server with values from .env
echo "Starting FastAPI server..."
uvicorn circ_toolbox.main:app --host ${API_HOST} --port ${API_PORT} --reload
















#!/bin/bash
set -e  # Exit on error if any command fails

echo "Starting backend container..."

# Load Conda environment
source /opt/conda/etc/profile.d/conda.sh
conda activate circrna_pipeline_env || { echo "Failed to activate Conda environment"; exit 1; }

# Load environment variables from .env using process_env.sh script
/app/process_env.sh

# Ensure database exists
if [ ! -f "${DATABASE_DIR}/${DATABASE_FILENAME}" ]; then
    echo "Database not found, creating..."
    python circ_toolbox/backend/database/init_db.py
fi

# Check if Alembic is initialized
if [ ! -f "${ALEMBIC_INI_PATH}" ]; then
    echo "Alembic configuration not found. Initializing..."
    alembic init circ_toolbox/backend/database/migrations
fi

# Run migrations (upgrade schema)
echo "Running database migrations..."
alembic -c "${ALEMBIC_INI_PATH}" upgrade head

# Populate initial data (e.g., create admin user)
echo "Running initial data script..."
python circ_toolbox/backend/scripts/initial_data.py || { echo "Initial data population failed"; exit 1; }

# Start the FastAPI server
echo "Starting FastAPI server..."
uvicorn circ_toolbox.main:app --host ${API_HOST} --port ${API_PORT} --reload











#!/bin/bash

set -e  # Exit on error if any command fails

echo "Starting backend container..."

# Load Conda environment
source /opt/conda/etc/profile.d/conda.sh
conda activate circrna_pipeline_env || { echo "Failed to activate Conda environment"; exit 1; }

# Load environment variables
/app/process_env.sh

# Ensure the database exists before running migrations
if [ ! -f "${DATABASE_DIR}/${DATABASE_FILENAME}" ]; then
    echo "Creating and initializing database..."
    python circ_toolbox/backend/scripts/init_db.py
fi

# Run Alembic migrations
echo "Applying database migrations..."
alembic upgrade head || { echo "Alembic migration failed"; exit 1; }

# Run initial data population (admin user)
echo "Creating admin user..."
python circ_toolbox/backend/scripts/create_admin_user.py || { echo "Initial admin creation failed"; exit 1; }

# Start the FastAPI server
echo "Starting FastAPI server..."
uvicorn circ_toolbox.main:app --host ${API_HOST} --port ${API_PORT} --reload
