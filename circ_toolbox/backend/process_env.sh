# circ_toolbox_project/circ_toolbox/backend/process_env.sh
#!/bin/bash

echo "Loading environment variables from .env file..."

while IFS='=' read -r key value; do
  if [[ ! $key =~ ^# && -n $key ]]; then
    export "$key"="$value"
  fi
done < /app/.env

echo "✅ Environment variables loaded successfully."