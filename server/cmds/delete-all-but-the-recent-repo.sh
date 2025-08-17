#!/bin/bash

# ==============================================================================
# WARNING: THIS SCRIPT PERMANENTLY DELETES ARTIFACTS. USE WITH EXTREME CAUTION.
# ==============================================================================
#
# This script deletes all but the most recently created version of a specific
# package in Google Artifact Registry.

# --- Configuration ---
# TODO: Fill in these values before running the script.
PROJECT_ID="returnable-469114"
LOCATION="europe-west1"         # The region of your repository, e.g., us-central1
REPOSITORY="cloud-run-source-deploy"     # The name of the repository
PACKAGE="test"           # The name of the package (e.g., your Docker image name)
# --- End Configuration ---


# Function to print a formatted header
print_header() {
    echo "======================================================================"
    echo "$1"
    echo "======================================================================"
}

# Validate that configuration is set
if [[ "$PROJECT_ID" == "your-gcp-project-id" ]]; then
    echo "ERROR: Please edit the script and set the PROJECT_ID variable."
    exit 1
fi

print_header "Configuration"
echo "Project:    $PROJECT_ID"
echo "Location:   $LOCATION"
echo "Repository: $REPOSITORY"
echo "Package:    $PACKAGE"
echo

# --- Step 1 & 2: List all versions and identify the ones to delete ---
# We list versions, sort by creation time descending (newest first),
# get only the version identifier (the digest), and then use `tail`
# to skip the first line (the newest version we want to keep).
print_header "Identifying versions to delete"

VERSIONS_TO_DELETE=$(gcloud artifacts versions list \
  --project="$PROJECT_ID" \
  --location="$LOCATION" \
  --repository="$REPOSITORY" \
  --package="$PACKAGE" \
  --sort-by="~CREATE_TIME" \
  --format="value(version)" \
  | tail -n +2)

# Check if there are any old versions to delete
if [[ -z "$VERSIONS_TO_DELETE" ]]; then
  echo "No older versions found to delete. The package has only one or zero versions."
  exit 0
fi

echo "The following older versions have been targeted for deletion:"
echo "--------------------------------------------------------------"
echo "$VERSIONS_TO_DELETE"
echo "--------------------------------------------------------------"
echo

# --- Step 3: Ask for user confirmation ---
read -p "Are you sure you want to permanently delete these versions? [y/N] " -r REPLY
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deletion cancelled by user."
    exit 1
fi

# --- Step 4: Loop and delete the identified versions ---
print_header "Starting Deletion Process"
for VERSION in $VERSIONS_TO_DELETE; do
  echo "Deleting version: $VERSION ..."
  gcloud artifacts versions delete "$VERSION" \
    --project="$PROJECT_ID" \
    --location="$LOCATION" \
    --repository="$REPOSITORY" \
    --package="$PACKAGE" \
    --quiet # Use --quiet to suppress the y/N prompt for each individual deletion
  
  # Check exit code for success/failure
  if [[ $? -eq 0 ]]; then
    echo "Successfully deleted $VERSION"
  else
    echo "ERROR: Failed to delete $VERSION"
  fi
  echo
done

print_header "Cleanup complete!"