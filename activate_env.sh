#!/bin/bash

# Activate the Conda environment
source ~/miniconda3/bin/activate circrna_pipeline_env_p3_10

# Set the PYTHONPATH to the project root (circ_toolbox_project)
export PYTHONPATH=$(pwd)
echo "PYTHONPATH set to: $PYTHONPATH"

# Load environment variables from .env file safely, ignoring comments and empty lines
while IFS='=' read -r key value; do
  # Ignore lines that start with '#' or are empty
  if [[ ! $key =~ ^# && -n $key ]]; then
    export "$key"="$value"
  fi
done < .env

echo "Environment variables loaded from .env file"

# Confirm the setup
echo "Conda environment 'circrna_pipeline_env' activated."
echo "Ready to start development!"


# Each time you start working, follow these steps:

# cd ~/Documentos/circ_toolbox_project
# source activate_env.sh

# Run the application with absolute imports:
# python -m circ_toolbox.main


# python -c "from circ_toolbox.config import DATABASE_URL; print(DATABASE_URL)"

# PYTHONPATH set to: /home/user/Documentos/circ_toolbox_project
# Environment variables loaded from .env file
# Conda environment 'circrna_pipeline_env' activated.
# Ready to start development!


