#!/bin/bash
# 🚀 Unified FastAPI User Management Integration Test Script
# This script runs core tests (authentication, user creation, profile updates, deletion, duplicate checks)
# as well as additional tests (password change, status flags update, invalid JSON, listing/pagination,
# authorization for listing, and edge cases).
#
# Run this script after initializing your database so that the following users exist:
# - regular_user (user@example.com)
# - update_user (updateuser@example.com) will be created in this script.
# - admin (admin@circtoolbox.com)
# - admin2 (admin2@example.com)
#
# All responses are printed via jq.

set -e  # Exit immediately if any command fails

echo "🔹 Starting Unified FastAPI User Management Tests..."

########################################
# 1. Admin Authentication
########################################
echo "🔹 Logging in as Admin..."
ADMIN_TOKEN=$(curl -s -X POST 'http://127.0.0.1:8000/api/v1/auth/jwt/login' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=admin@circtoolbox.com&password=Admin@123' | jq -r '.access_token')
if [ -z "$ADMIN_TOKEN" ] || [ "$ADMIN_TOKEN" = "null" ]; then
  echo "❌ Admin login failed! Exiting."
  exit 1
fi
echo "✅ Admin Token Retrieved!"
echo "$ADMIN_TOKEN"
 
########################################
# 2. Create a Regular User
########################################
echo "🔹 Creating Regular User..."
REGULAR_USER_ID=$(curl -s -X POST 'http://127.0.0.1:8000/api/v1/admin/users' \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "email": "user@example.com",
        "password": "User@123",
        "username": "regular_user",
        "is_active": true,
        "is_superuser": false,
        "is_verified": true
     }' | jq -r '.id')
if [ -z "$REGULAR_USER_ID" ] || [ "$REGULAR_USER_ID" = "null" ]; then
  echo "❌ Regular User creation failed! Exiting."
  exit 1
fi
echo "✅ Regular User ID: $REGULAR_USER_ID"
 
########################################
# 3. Create Another Admin User
########################################
echo "🔹 Creating Another Admin User..."
SECOND_ADMIN_ID=$(curl -s -X POST 'http://127.0.0.1:8000/api/v1/admin/users' \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "email": "admin2@example.com",
        "password": "Admin@123",
        "username": "admin2",
        "is_active": true,
        "is_superuser": true,
        "is_verified": true
     }' | jq -r '.id')
if [ -z "$SECOND_ADMIN_ID" ] || [ "$SECOND_ADMIN_ID" = "null" ]; then
  echo "❌ Second Admin creation failed! Exiting."
  exit 1
fi
echo "✅ Second Admin ID: $SECOND_ADMIN_ID"
 
########################################
# 4. Retrieve the Current Admin's User ID
########################################
echo "🔹 Retrieving Admin User ID..."
ADMIN_USER_ID=$(curl -s -X GET 'http://127.0.0.1:8000/api/v1/users/me' \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq -r '.id')
if [ -z "$ADMIN_USER_ID" ] || [ "$ADMIN_USER_ID" = "null" ]; then
  echo "❌ Failed to retrieve Admin User ID! Exiting."
  exit 1
fi
echo "✅ Admin User ID: $ADMIN_USER_ID"
 
########################################
# 5. Profile Update Tests (Core)
########################################
echo "🔹 Creating New Regular User for Profile Update Test..."
NEW_REGULAR_USER_ID=$(curl -s -X POST 'http://127.0.0.1:8000/api/v1/admin/users' \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "email": "updateuser@example.com",
        "password": "User@123",
        "username": "update_user",
        "is_active": true,
        "is_superuser": false,
        "is_verified": true
     }' | jq -r '.id')
if [ -z "$NEW_REGULAR_USER_ID" ] || [ "$NEW_REGULAR_USER_ID" = "null" ]; then
  echo "❌ New Regular User creation for update test failed! Exiting."
  exit 1
fi
echo "✅ New Regular User ID: $NEW_REGULAR_USER_ID"

echo "🔹 Logging in as New Regular User..."
REGULAR_USER_TOKEN=$(curl -s -X POST 'http://127.0.0.1:8000/api/v1/auth/jwt/login' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=updateuser@example.com&password=User@123' | jq -r '.access_token')
if [ -z "$REGULAR_USER_TOKEN" ] || [ "$REGULAR_USER_TOKEN" = "null" ]; then
  echo "❌ Regular User login failed! Exiting."
  exit 1
fi
echo "✅ Regular User Token Retrieved: $REGULAR_USER_TOKEN"

# 5a. Regular User self-update (should succeed)
echo "🔹 Regular User updating its own profile..."
UPDATE_SELF_RESPONSE=$(curl -s -X PATCH 'http://127.0.0.1:8000/api/v1/users/me' \
  -H "Authorization: Bearer $REGULAR_USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username": "updated_regular_user"}')
echo "$UPDATE_SELF_RESPONSE" | jq '.'
UPDATED_USERNAME=$(echo "$UPDATE_SELF_RESPONSE" | jq -r '.username')
if [ "$UPDATED_USERNAME" = "updated_regular_user" ]; then
  echo "✅ Regular User self-update successful. New username: $UPDATED_USERNAME"
else
  echo "❌ Regular User self-update failed. Response: $UPDATE_SELF_RESPONSE"
fi

# 5b. Regular User attempts to update another user's profile (should fail)
echo "🔹 Regular User attempting to update another user's profile (should fail)..."
UPDATE_OTHER_RESPONSE=$(curl -s -X PATCH "http://127.0.0.1:8000/api/v1/admin/users/$ADMIN_USER_ID" \
  -H "Authorization: Bearer $REGULAR_USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username": "hacked_admin"}')
echo "📌 Response for updating another user:"
echo "$UPDATE_OTHER_RESPONSE" | jq '.'
if echo "$UPDATE_OTHER_RESPONSE" | grep -qi "Forbidden"; then
  echo "✅ Regular User not allowed to update another user's profile."
else
  echo "❌ Regular User was able to update another user's profile (unexpected)."
fi

# 5c. Admin self-update (should succeed)
echo "🔹 Admin updating its own profile..."
ADMIN_UPDATE_RESPONSE=$(curl -s -X PATCH 'http://127.0.0.1:8000/api/v1/users/me' \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin_updated"}')
echo "$ADMIN_UPDATE_RESPONSE" | jq '.'
ADMIN_UPDATED_USERNAME=$(echo "$ADMIN_UPDATE_RESPONSE" | jq -r '.username')
if [ "$ADMIN_UPDATED_USERNAME" = "admin_updated" ]; then
  echo "✅ Admin self-update successful. New username: $ADMIN_UPDATED_USERNAME"
else
  echo "❌ Admin self-update failed. Response: $ADMIN_UPDATE_RESPONSE"
fi

# 5d. Admin updating second admin's profile (should succeed)
echo "🔹 Admin updating second admin's profile..."
ADMIN_UPDATE_ADMIN_RESPONSE=$(curl -s -X PATCH "http://127.0.0.1:8000/api/v1/admin/users/$SECOND_ADMIN_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin2_updated"}')
echo "$ADMIN_UPDATE_ADMIN_RESPONSE" | jq '.'
ADMIN2_UPDATED_USERNAME=$(echo "$ADMIN_UPDATE_ADMIN_RESPONSE" | jq -r '.username')
if [ "$ADMIN2_UPDATED_USERNAME" = "admin2_updated" ]; then
  echo "✅ Admin updated second admin's profile successfully. New username: $ADMIN2_UPDATED_USERNAME"
else
  echo "❌ Admin update of second admin failed. Response: $ADMIN_UPDATE_ADMIN_RESPONSE"
fi

# 5e. Admin updating a regular user's profile (should succeed)
echo "🔹 Creating another Regular User for Admin update test..."
ANOTHER_REGULAR_USER_ID=$(curl -s -X POST 'http://127.0.0.1:8000/api/v1/admin/users' \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "email": "user2@example.com",
        "password": "User@123",
        "username": "regular_user2",
        "is_active": true,
        "is_superuser": false,
        "is_verified": true
     }' | jq -r '.id')
if [ -z "$ANOTHER_REGULAR_USER_ID" ] || [ "$ANOTHER_REGULAR_USER_ID" = "null" ]; then
  echo "❌ Regular User2 creation failed! Exiting."
  exit 1
fi
echo "✅ Regular User2 ID: $ANOTHER_REGULAR_USER_ID"

echo "🔹 Admin updating Regular User2's profile..."
ADMIN_UPDATE_REGULAR_RESPONSE=$(curl -s -X PATCH "http://127.0.0.1:8000/api/v1/admin/users/$ANOTHER_REGULAR_USER_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username": "regular_user2_updated"}')
echo "$ADMIN_UPDATE_REGULAR_RESPONSE" | jq '.'
UPDATED_REGULAR_USERNAME=$(echo "$ADMIN_UPDATE_REGULAR_RESPONSE" | jq -r '.username')
if [ "$UPDATED_REGULAR_USERNAME" = "regular_user2_updated" ]; then
  echo "✅ Admin updated Regular User2's profile successfully. New username: $UPDATED_REGULAR_USERNAME"
else
  echo "❌ Admin update of Regular User2 failed. Response: $ADMIN_UPDATE_REGULAR_RESPONSE"
fi

########################################
# 6. Deletion Tests (Core)
########################################
echo "🔹 Deleting Second Admin..."
DELETE_SECOND_ADMIN_RESPONSE=$(curl -s -X DELETE "http://127.0.0.1:8000/api/v1/admin/users/$SECOND_ADMIN_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN")
echo "📌 Response for Second Admin Deletion:"
echo "$DELETE_SECOND_ADMIN_RESPONSE"
if [ -z "$DELETE_SECOND_ADMIN_RESPONSE" ] || [ "$DELETE_SECOND_ADMIN_RESPONSE" = "null" ] || [ "$DELETE_SECOND_ADMIN_RESPONSE" = "" ]; then
  echo "✅ Second Admin Deletion: WORKING."
else
  echo "❌ Second Admin Deletion: FAILED."
fi

echo "🔹 Attempting to Delete Last Admin (should be prevented)..."
DELETE_LAST_ADMIN_RESPONSE=$(curl -s -X DELETE "http://127.0.0.1:8000/api/v1/admin/users/$ADMIN_USER_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN")
echo "📌 Response for Last Admin Deletion:"
echo "$DELETE_LAST_ADMIN_RESPONSE" | jq '.'
if echo "$DELETE_LAST_ADMIN_RESPONSE" | grep -qi "Cannot delete the last superuser"; then
  echo "✅ Last Admin Deletion Prevention: WORKING."
else
  echo "❌ Last Admin Deletion Prevention: FAILED."
fi

echo "🚀 Core Tests Completed!"

########################
# 7️ Create User with Existing Email (Should Fail) 
######################## 
echo "🔹 Attempting to create a Regular User with an existing email..." 
CREATE_REGULAR_USER_ERROR_RESPONSE=$(curl -s -X POST 'http://127.0.0.1:8000/api/v1/admin/users' \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
      "email": "user@example.com",
      "password": "User@123",
      "username": "regular_user",
      "is_active": true,
      "is_superuser": false,
      "is_verified": true
    }' )
  # Re-using the email used in Step 2 "password": "User@123", "username": "duplicated_user", "is_active": true, "is_superuser": false, "is_verified": true }' )
echo "$CREATE_REGULAR_USER_ERROR_RESPONSE" | jq '.'
if echo "$CREATE_REGULAR_USER_ERROR_RESPONSE" | grep -qi "already exists"; then
  echo "✅ Error as expected: User with this email already exists. No user created." 
else 
  echo "❌ Test failed: User with the same email was created. Response: $CREATE_REGULAR_USER_ERROR_RESPONSE" 
fi 
  
  
######################## 
# 8️ Update User Email to Existing Email (Should Fail) 
######################## 
echo "🔹 Attempting to update Regular User's email to an existing user's email..." 
UPDATE_USER_EMAIL_ERROR_RESPONSE=$(curl -s -X PATCH "http://127.0.0.1:8000/api/v1/admin/users/$NEW_REGULAR_USER_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com"}' ) 
  # Trying to update email to an existing one 
echo "$UPDATE_USER_EMAIL_ERROR_RESPONSE" | jq '.'

if echo "$UPDATE_USER_EMAIL_ERROR_RESPONSE" | grep -qi "already exists"; then 
  echo "✅ Error as expected: Email already taken. User emails cannot be updated to an existing email." 
else 
  echo "❌ Test failed: Email was updated to an already existing email. Response: $UPDATE_USER_EMAIL_ERROR_RESPONSE" 
fi

########################################
# 9. Additional Tests
########################################

########################################
# A. Password Change Test
########################################
# Regular users should update their own password only via the /users/me endpoint.
echo "🔹 Regular User attempting to update its own password via /users/me (should succeed if supported)..."
PASSWORD_UPDATE_SELF_RESPONSE=$(curl -s -X PATCH 'http://127.0.0.1:8000/api/v1/users/me' \
  -H "Authorization: Bearer $REGULAR_USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"password": "NewUser@123"}')
echo "$PASSWORD_UPDATE_SELF_RESPONSE" | jq '.'
if echo "$PASSWORD_UPDATE_SELF_RESPONSE" | grep -qi "error"; then
  echo "❌ Regular User not allowed to update its own password via /users/me."
else
  echo "✅ Regular User password update via /users/me succeeded."
fi

# Also test that a regular user using its token cannot access the admin endpoint for password updates.
echo "🔹 Regular User attempting to update password via admin endpoint (should fail)..."
PASSWORD_UPDATE_ADMIN_RESPONSE=$(curl -s -X PATCH "http://127.0.0.1:8000/api/v1/admin/users/$NEW_REGULAR_USER_ID" \
  -H "Authorization: Bearer $REGULAR_USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"password": "ShouldNotWork"}')
echo "$PASSWORD_UPDATE_ADMIN_RESPONSE" | jq '.'
if echo "$PASSWORD_UPDATE_ADMIN_RESPONSE" | grep -qi "Forbidden"; then
  echo "✅ Regular User not allowed to update password via admin endpoint."
else
  echo "❌ Regular User update password via admin endpoint unexpectedly succeeded."
fi

# ----------
echo "🔹 Retrieving current profile for Regular User (updateuser@example.com)..."
CURRENT_REGULAR_PROFILE=$(curl -s -X GET 'http://127.0.0.1:8000/api/v1/users/me' \
  -H "Authorization: Bearer $REGULAR_USER_TOKEN")
CURRENT_REGULAR_ID=$(echo "$CURRENT_REGULAR_PROFILE" | jq -r '.id')
echo "✅ Current Regular User ID: $CURRENT_REGULAR_ID"

echo "🔹 Admin User updating current Regular User password via admin endpoint..."
PASSWORD_UPDATE_RESPONSE=$(curl -s -X PATCH "http://127.0.0.1:8000/api/v1/admin/users/$CURRENT_REGULAR_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"password": "NewUser@123"}')
echo "$PASSWORD_UPDATE_RESPONSE" | jq '.'

echo "🔹 Testing login with new password..."
NEW_REGULAR_TOKEN=$(curl -s -X POST 'http://127.0.0.1:8000/api/v1/auth/jwt/login' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d "username=updateuser@example.com&password=NewUser@123" | jq -r '.access_token')
if [ -z "$NEW_REGULAR_TOKEN" ] || [ "$NEW_REGULAR_TOKEN" = "null" ]; then
  echo "❌ Login with new password failed!"
else
  echo "✅ Login with new password succeeded."
fi

echo "🔹 Testing login with old password (should fail)..."
OLD_REGULAR_TOKEN=$(curl -s -X POST 'http://127.0.0.1:8000/api/v1/auth/jwt/login' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d "username=updateuser@example.com&password=User@123" | jq -r '.access_token')
if [ -z "$OLD_REGULAR_TOKEN" ] || [ "$OLD_REGULAR_TOKEN" = "null" ]; then
  echo "✅ Login with old password correctly failed."
else
  echo "❌ Login with old password unexpectedly succeeded."
fi

########################################
# B. Status Flags Update Test
########################################
echo "🔹 Admin updating Regular User (updateuser@example.com) status flags TO FALSE..."
STATUS_UPDATE_RESPONSE=$(curl -s -X PATCH "http://127.0.0.1:8000/api/v1/admin/users/$CURRENT_REGULAR_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false, "is_verified": false}')
echo "$STATUS_UPDATE_RESPONSE" | jq '.'
echo "🔹 Retrieving updated profile for status flags..."
UPDATED_PROFILE=$(curl -s -X GET "http://127.0.0.1:8000/api/v1/admin/users/$CURRENT_REGULAR_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN")
echo "$UPDATED_PROFILE" | jq '.'

echo "🔹 Admin updating Regular User (updateuser@example.com) status  BACK TO TRUE..."
STATUS_UPDATE_RESPONSE=$(curl -s -X PATCH "http://127.0.0.1:8000/api/v1/admin/users/$CURRENT_REGULAR_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_active": true, "is_verified": true}')
echo "$STATUS_UPDATE_RESPONSE" | jq '.'
echo "🔹 Retrieving updated profile for status flags..."
UPDATED_PROFILE=$(curl -s -X GET "http://127.0.0.1:8000/api/v1/admin/users/$CURRENT_REGULAR_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN")
echo "$UPDATED_PROFILE" | jq '.'

########################################
# C. Invalid Data Tests
########################################
echo "🔹 Sending invalid JSON payload to update endpoint..."
INVALID_PAYLOAD_RESPONSE=$(curl -s -X PATCH "http://127.0.0.1:8000/api/v1/admin/users/$CURRENT_REGULAR_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username": updated_regular_user}')
echo "Response for invalid JSON payload:"
echo "$INVALID_PAYLOAD_RESPONSE" | jq '.'

echo "🔹 Sending empty JSON payload to update endpoint..."
EMPTY_PAYLOAD_RESPONSE=$(curl -s -X PATCH "http://127.0.0.1:8000/api/v1/admin/users/$CURRENT_REGULAR_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}')
echo "Response for empty JSON payload:"
echo "$EMPTY_PAYLOAD_RESPONSE" | jq '.'

########################################
# D. Listing and Pagination Test
########################################
echo "🔹 Listing users with skip=0, limit=2..."
LIST_RESPONSE_PAGE1=$(curl -s -X GET "http://127.0.0.1:8000/api/v1/admin/users?skip=0&limit=2" \
  -H "Authorization: Bearer $ADMIN_TOKEN")
echo "$LIST_RESPONSE_PAGE1" | jq '.'

echo "🔹 Listing users with skip=2, limit=2..."
LIST_RESPONSE_PAGE2=$(curl -s -X GET "http://127.0.0.1:8000/api/v1/admin/users?skip=2&limit=2" \
  -H "Authorization: Bearer $ADMIN_TOKEN")
echo "$LIST_RESPONSE_PAGE2" | jq '.'

########################################
# E. Authorization Check for Listing Users
########################################
echo "🔹 Attempting to list users with Regular User token (should fail)..."
LIST_REGULAR_RESPONSE=$(curl -s -X GET "http://127.0.0.1:8000/api/v1/admin/users?skip=0&limit=2" \
  -H "Authorization: Bearer $NEW_REGULAR_TOKEN")
echo "Response for regular user listing attempt:"
echo "$LIST_REGULAR_RESPONSE" | jq '.'

########################################
# F. Edge Cases
########################################
echo "🔹 Attempting to update user with empty payload (should return no change)..."
EMPTY_UPDATE_RESPONSE=$(curl -s -X PATCH "http://127.0.0.1:8000/api/v1/admin/users/$CURRENT_REGULAR_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}')
echo "$EMPTY_UPDATE_RESPONSE" | jq '.'

echo "🔹 Attempting to update user with the same email as itself (should succeed)..."
SAME_EMAIL_UPDATE_RESPONSE=$(curl -s -X PATCH "http://127.0.0.1:8000/api/v1/admin/users/$CURRENT_REGULAR_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email": "updateuser@example.com"}')
echo "$SAME_EMAIL_UPDATE_RESPONSE" | jq '.'

if echo "$SAME_EMAIL_UPDATE_RESPONSE" | grep -qi "already exists"; then 
  echo "❌ Test failed: Updating with the same email should succeed (backend uniqueness check must be adjusted)."
else 
  echo "✅ Update with same email as current succeeded (or no error returned)."
fi


echo "🔹 Logging in as Regular User again for same email update test..." 
REGULAR_USER_TOKEN=$(curl -s -X POST 'http://127.0.0.1:8000/api/v1/auth/jwt/login' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=updateuser@example.com&password=NewUser@123' | jq -r '.access_token')

echo "$REGULAR_USER_TOKEN"
if [ -z "$REGULAR_USER_TOKEN" ] || [ "$REGULAR_USER_TOKEN" = "null" ]; then 
    echo "❌ Regular User re-login failed! Exiting." 
else
    echo "✅ Regular User Token Retrieved: $REGULAR_USER_TOKEN"
fi

echo "🔹 Attempting to update user with the same email as itself (should succeed)..."
# For self-update, use the /users/me endpoint so that uniqueness check does not block
SAME_EMAIL_UPDATE_RESPONSE=$(curl -s -X PATCH "http://127.0.0.1:8000/api/v1/users/me" \
  -H "Authorization: Bearer $REGULAR_USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email": "updateuser@example.com"}')
echo "$SAME_EMAIL_UPDATE_RESPONSE" | jq '.'
if echo "$SAME_EMAIL_UPDATE_RESPONSE" | grep -qi "already exists"; then 
  echo "❌ Test failed: Updating with the same email should succeed (backend uniqueness check must be adjusted)."
else 
  echo "✅ Update with same email as current succeeded (or no error returned)."
fi


echo "🚀 Additional Tests Completed!"
echo "🚀 Unified FastAPI User Management Tests Completed!"
