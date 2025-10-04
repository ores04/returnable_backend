#!/bin/bash

# change dir to dockerfile location
cd ../../


# Configuration
PROJECT_ID="effortless-474015"
REGION="europe-west1"
REPOSITORY="effortless-backend"
IMAGE_NAME="effortless-backend-image"
TAG="latest"

# Full image path
FULL_IMAGE_PATH="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:${TAG}"

echo "🔨 Building Docker image..."
docker buildx build --platform linux/amd64 -t ${IMAGE_NAME}:${TAG} .

if [ $? -ne 0 ]; then
    echo "❌ Docker build failed!"
    exit 1
fi

echo "✅ Build successful!"

echo "🏷️  Tagging image..."
docker tag ${IMAGE_NAME}:${TAG} ${FULL_IMAGE_PATH}

echo "🚀 Pushing to Google Artifact Registry..."
docker push ${FULL_IMAGE_PATH}

if [ $? -ne 0 ]; then
    echo "❌ Push failed!"
    exit 1
fi

echo "✅ Successfully pushed ${FULL_IMAGE_PATH}"
echo ""
echo "To deploy to Cloud Run, run:"
echo "gcloud run deploy effortless-backend --image ${FULL_IMAGE_PATH} --region ${REGION}"