#!/bin/bash
# =========================================================================================
# 🚀 Unified Resource Routes Testing Script (Extended with Suggestions)
# This script tests resource endpoints (create, list, update, patch, delete, get by ID, species list)
# It uses curl to interact with the API, and jq to parse JSON responses.
# Prerequisites:
#   - API is running at http://127.0.0.1:8000
#   - Test files exist on disk (one for each resource type)
#   - 'jq' is installed
# =========================================================================================

set -e  # Exit immediately if any command fails

# --------------------------
# GLOBALS + CONFIG
# --------------------------
BASE_URL="http://127.0.0.1:8000/api/v1"
ADMIN_LOGIN_URL="$BASE_URL/auth/jwt/login"
ADMIN_USERS_URL="$BASE_URL/admin/users"
RESOURCES_URL="$BASE_URL/resources"
USERS_ME_URL="$BASE_URL/users/me"
SPECIES_URL="$RESOURCES_URL/species/"

# Paths to your test files (ensure these exist)
GENOME_FILE="/home/hugo/Documentos/WORKSTATION/hybrid_fragaria/Fragaria_x_ananassa_Reference_Genome_v1.0_FANhybrid_r1.2_scaffolds.fasta"
ANNOTATION_FILE="/home/hugo/Documentos/WORKSTATION/hybrid_fragaria/Fragaria_x_ananassa_Reference_Genome_v1.0_FANhybrid_r1.2_gene.gff3"
PEPTIDE_FILE="/home/hugo/Documentos/WORKSTATION/hybrid_fragaria/Fragaria_x_ananassa_Reference_Genome_v1.0_FANhybrid_r1.2_pep.fasta"

# --------------------------
# HELPER FUNCTIONS
# --------------------------

# Structured logging with time stamp + step notation
function log_step() {
  local step_message="$1"
  echo "[STEP] $(date '+%Y-%m-%d %H:%M:%S') - $step_message"
}

# cURL wrapper to capture both response body and HTTP status
# Usage:
#   do_curl <METHOD> <URL> <HEADERS> <DATA>
#   Returns two variables: $http_body and $http_code
function do_curl() {
  local method=$1
  local url=$2
  shift 2
  # Save all other arguments (headers, form fields, etc.)
  # to a temporary array so we can pass them to curl.
  local curl_args=("$@")

  # Capture the response body in a temp file, status code in another variable
  local tmpfile_body
  tmpfile_body=$(mktemp)

  http_code=$(curl -s -o "$tmpfile_body" -w "%{http_code}" -X "$method" "$url" "${curl_args[@]}")
  http_body=$(cat "$tmpfile_body")
  rm -f "$tmpfile_body"
}

# Quick check to ensure HTTP code is expected (e.g., 200 or 201)
# If not, we print the body and exit
function check_http_code() {
  local expected_code="$1"
  if [ "$http_code" -ne "$expected_code" ]; then
    echo "❌ Expected HTTP $expected_code but got $http_code."
    echo "Response body: $http_body"
    exit 1
  fi
}

# --------------------------
# 1. Admin Authentication
# --------------------------
log_step "1) Logging in as Admin..."
do_curl "POST" "$ADMIN_LOGIN_URL" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=admin@circtoolbox.com&password=Admin@123'
check_http_code 200

ADMIN_TOKEN=$(echo "$http_body" | jq -r '.access_token')
if [ -z "$ADMIN_TOKEN" ] || [ "$ADMIN_TOKEN" = "null" ]; then
  echo "❌ Admin login failed! Exiting."
  exit 1
fi
echo "✅ Admin Token Retrieved: $ADMIN_TOKEN"

# --------------------------
# 2. Create Resource Users
# --------------------------
log_step "2) Creating Resource Regular User..."
do_curl "POST" "$ADMIN_USERS_URL" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "email": "resource_regular_user@example.com",
        "password": "User@123",
        "username": "resource_regular_user",
        "is_active": true,
        "is_superuser": false,
        "is_verified": true
      }'
check_http_code 200

REGULAR_USER_ID=$(echo "$http_body" | jq -r '.id')
if [ -z "$REGULAR_USER_ID" ] || [ "$REGULAR_USER_ID" = "null" ]; then
  echo "❌ Regular resource user creation failed! Exiting."
  exit 1
fi
echo "✅ Regular Resource User ID: $REGULAR_USER_ID"

log_step "Creating Resource Admin User..."
do_curl "POST" "$ADMIN_USERS_URL" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "email": "resource_admin_user@example.com",
        "password": "Admin@123",
        "username": "resource_admin_user",
        "is_active": true,
        "is_superuser": true,
        "is_verified": true
      }'
check_http_code 200

SECOND_ADMIN_ID=$(echo "$http_body" | jq -r '.id')
if [ -z "$SECOND_ADMIN_ID" ] || [ "$SECOND_ADMIN_ID" = "null" ]; then
  echo "❌ Resource admin user creation failed! Exiting."
  exit 1
fi
echo "✅ Resource Admin User ID: $SECOND_ADMIN_ID"

# --------------------------
# 3. Retrieve Current Admin's User ID
# --------------------------
log_step "3) Retrieving Admin User ID..."
do_curl "GET" "$USERS_ME_URL" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
check_http_code 200

ADMIN_USER_ID=$(echo "$http_body" | jq -r '.id')
if [ -z "$ADMIN_USER_ID" ] || [ "$ADMIN_USER_ID" = "null" ]; then
  echo "❌ Failed to retrieve Admin User ID! Exiting."
  exit 1
fi
echo "✅ Admin User ID: $ADMIN_USER_ID"

# --------------------------
# 4) Retrieve Regular User Token
# --------------------------
log_step "4) Logging in as Regular User..."
do_curl "POST" "$ADMIN_LOGIN_URL" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=resource_regular_user@example.com&password=User@123'
check_http_code 200

REGULAR_TOKEN=$(echo "$http_body" | jq -r '.access_token')
if [ -z "$REGULAR_TOKEN" ] || [ "$REGULAR_TOKEN" = "null" ]; then
  echo "❌ Regular user login failed! Exiting."
  exit 1
fi
echo "✅ Regular User Token Retrieved: $REGULAR_TOKEN"

# --------------------------
# 5. Create Resources (File Upload Tests)
# --------------------------
log_step "5) Creating a GENOME resource as Admin..."
do_curl "POST" "$RESOURCES_URL/" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -F "name=TestGenomeResource" \
  -F "resource_type=GENOME" \
  -F "species=TestSpecies" \
  -F "version=1.0" \
  -F "file=@${GENOME_FILE}" \
  -F "force_overwrite=false"
check_http_code 200
RESOURCE_GENOME="$http_body"
echo "Response: $RESOURCE_GENOME"

RESOURCE_ID=$(echo "$RESOURCE_GENOME" | jq -r '.id')
echo "Saved RESOURCE_ID for further tests: $RESOURCE_ID"

log_step "Creating an ANNOTATION resource as Admin..."
do_curl "POST" "$RESOURCES_URL/" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -F "name=TestAnnotationResource" \
  -F "resource_type=ANNOTATION" \
  -F "species=TestSpecies" \
  -F "version=1.0" \
  -F "file=@${ANNOTATION_FILE}" \
  -F "force_overwrite=false"
check_http_code 200
echo "Response: $http_body"

log_step "Creating a PEPTIDE resource as Admin..."
do_curl "POST" "$RESOURCES_URL/" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -F "name=TestReferenceResource" \
  -F "resource_type=PEPTIDE" \
  -F "species=TestSpecies" \
  -F "version=1.0" \
  -F "file=@${PEPTIDE_FILE}" \
  -F "force_overwrite=false"
check_http_code 200
echo "Response: $http_body"

log_step "Creating a GENOME resource as Regular User..."
do_curl "POST" "$RESOURCES_URL/" \
  -H "Authorization: Bearer $REGULAR_TOKEN" \
  -F "name=UserGenomeResource" \
  -F "resource_type=GENOME" \
  -F "species=UserSpecies" \
  -F "version=1.0" \
  -F "file=@${GENOME_FILE}" \
  -F "force_overwrite=false"
check_http_code 200

RESOURCE_REGULAR="$http_body"
REGULAR_RESOURCE_ID=$(echo "$RESOURCE_REGULAR" | jq -r '.id')
echo "Regular user's resource ID: $REGULAR_RESOURCE_ID"

# --------------------------
# 6. Listing Resources
# --------------------------
log_step "6) Listing resources with filter 'GENOME'..."
do_curl "GET" "$RESOURCES_URL/?limit=10&offset=0&resource_type=GENOME" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
check_http_code 200

echo "Resources listing:"
echo "$http_body" | jq .

# --------------------------
# 7. GET by ID Before Update
# --------------------------
log_step "7) GET resource by ID (before update) to verify fields..."
do_curl "GET" "$RESOURCES_URL/$RESOURCE_ID/" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
check_http_code 200

echo "Current resource data (before update):"
echo "$http_body" | jq .

# --------------------------
# 8. Update Resource (PUT) as Admin
# --------------------------
log_step "8) Updating resource $RESOURCE_ID as Admin (PUT)..."
do_curl "PUT" "$RESOURCES_URL/$RESOURCE_ID/" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -F "name=UpdatedGenomeResource" \
  -F "resource_type=GENOME" \
  -F "species=UpdatedSpecies" \
  -F "version=2.0" \
  -F "file=@${GENOME_FILE}" \
  -F "force_overwrite=false"
check_http_code 200

echo "Update Response: $http_body"

# --------------------------
# 9. GET by ID After Update
# --------------------------
log_step "9) GET resource by ID (after update) to verify changes..."
do_curl "GET" "$RESOURCES_URL/$RESOURCE_ID/" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
check_http_code 200

echo "Updated resource data:"
echo "$http_body" | jq .

# --------------------------
# 10. Update Resource as the Owner (Regular User)
# --------------------------
log_step "10) Updating resource $REGULAR_RESOURCE_ID as the owner..."
do_curl "PUT" "$RESOURCES_URL/$REGULAR_RESOURCE_ID/" \
  -H "Authorization: Bearer $REGULAR_TOKEN" \
  -F "name=UpdatedUserGenomeResource" \
  -F "resource_type=GENOME" \
  -F "species=UpdatedUserSpecies" \
  -F "version=2.0" \
  -F "file=@${GENOME_FILE}" \
  -F "force_overwrite=false"
check_http_code 200

echo "Owner update response: $http_body"

# --------------------------
# 11. Attempt Unauthorized Update (Regular User -> Another’s Resource)
# --------------------------
log_step "11) Attempting to update resource $RESOURCE_ID as a regular user (should fail)..."
do_curl "PUT" "$RESOURCES_URL/$RESOURCE_ID/" \
  -H "Authorization: Bearer $REGULAR_TOKEN" \
  -F "name=ShouldNotWork" \
  -F "resource_type=GENOME" \
  -F "species=UnauthorizedUpdate" \
  -F "version=99.9" \
  -F "file=@${GENOME_FILE}" \
  -F "force_overwrite=false"

# Expecting 403 here
if [ "$http_code" -eq 403 ]; then
  echo "✅ Unauthorized update blocked as expected. Response: $http_body"
else
  echo "❌ Expected 403 but got $http_code. Body: $http_body"
  exit 1
fi

# --------------------------
# 12. PATCH (Partial Update) if Supported
# --------------------------
log_step "12) Attempting partial update (PUT, NOT PATCH) on $REGULAR_RESOURCE_ID (resource owner)..."
# Example: only updating species field
do_curl "PUT" "$RESOURCES_URL/$REGULAR_RESOURCE_ID/" \
  -H "Authorization: Bearer $REGULAR_TOKEN" \
  -F "species=PatchUpdatedUserSpecies"

# If your API returns 200 for patch success:
check_http_code 200

echo "PATCH update response: $http_body"

log_step "Verifying resource post-patch with GET..."
do_curl "GET" "$RESOURCES_URL/$REGULAR_RESOURCE_ID/" \
  -H "Authorization: Bearer $REGULAR_TOKEN"
check_http_code 200

echo "Resource data after PATCH:"
echo "$http_body" | jq .

# --------------------------
# 13. Attempting Unauthorized Deletion
# --------------------------
log_step "13) Attempting unauthorized deletion (regular user) on resource $RESOURCE_ID..."
do_curl "DELETE" "$RESOURCES_URL/$RESOURCE_ID/" \
  -H "Authorization: Bearer $REGULAR_TOKEN"

# Expect 403
if [ "$http_code" -eq 403 ]; then
  echo "✅ Unauthorized deletion blocked as expected. Response: $http_body"
else
  echo "❌ Expected 403 but got $http_code. Body: $http_body"
  exit 1
fi

# --------------------------
# 14. Delete Resource as Admin
# --------------------------
log_step "14) Deleting resource $RESOURCE_ID as Admin..."
do_curl "DELETE" "$RESOURCES_URL/$RESOURCE_ID/" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
check_http_code 200

echo "Delete Response: $http_body"

# --------------------------
# 15. Verify Resource is Deleted
# --------------------------
log_step "15) GET resource by ID after deletion (should be 404)..."
do_curl "GET" "$RESOURCES_URL/$RESOURCE_ID/" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

if [ "$http_code" -eq 404 ]; then
  echo "✅ Resource not found, as expected."
else
  echo "❌ Expected 404 but got $http_code. Body: $http_body"
  exit 1
fi

# --------------------------
# 16. Get Species List
# --------------------------
log_step "16) Retrieving species list..."
do_curl "GET" "$SPECIES_URL" -H "Authorization: Bearer $ADMIN_TOKEN"
check_http_code 200

echo "Species List:" 
echo "$http_body" | jq .

# --------------------------
# 17. (Optional) Parameterized Testing Example
# --------------------------
# In a real scenario, you might have a function that loops over multiple
# resource types or versions. For demonstration, we show minimal usage.

function create_resource_param() {
  local rtype="$1"
  local sp="$2"
  local ver="$3"
  local filepath="$4"
  log_step "Parameterized creation: resource_type='$rtype', species='$sp', version='$ver'"
  do_curl "POST" "$RESOURCES_URL/" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -F "name=ParamTestResource" \
    -F "resource_type=$rtype" \
    -F "species=$sp" \
    -F "version=$ver" \
    -F "file=@${filepath}" \
    -F "force_overwrite=false"
  if [ "$http_code" -eq 200 ]; then
    local new_id
    new_id=$(echo "$http_body" | jq -r '.id')
    echo "Created param resource ID: $new_id"
  else
    echo "❌ Param creation failed with code $http_code: $http_body"
  fi
}

log_step "17) Parameterized test: creating additional resources for demonstration..."
create_resource_param "GENOME" "ParamSpecies1" "1.0" "$GENOME_FILE"
create_resource_param "ANNOTATION" "ParamSpecies1" "2.0" "$ANNOTATION_FILE"
create_resource_param "PEPTIDE" "ParamSpecies2" "1.5" "$PEPTIDE_FILE"

echo "✅ All tests executed successfully."
