#!/bin/bash

# change dir to dockerfile location
cd ../../

# Define variables
REGISTRY="registry.digitalocean.com/effortless-backend"
IMAGE_NAME="returnable-web"
TAG="latest"
FULL_IMAGE_NAME="${REGISTRY}/${IMAGE_NAME}:${TAG}"

echo "Building Docker image for linux/amd64..."
docker build --platform linux/amd64 -t ${IMAGE_NAME}:${TAG} -f Dockerfile .

if [ $? -ne 0 ]; then
    echo "Error: Docker build failed"
    exit 1
fi

echo "Tagging image for DigitalOcean registry..."
docker tag ${IMAGE_NAME}:${TAG} ${FULL_IMAGE_NAME}

if [ $? -ne 0 ]; then
    echo "Error: Docker tag failed"
    exit 1
fi

echo "Pushing image to DigitalOcean registry..."
docker push ${FULL_IMAGE_NAME}

if [ $? -ne 0 ]; then
    echo "Error: Docker push failed"
    exit 1
fi

echo "Successfully pushed ${FULL_IMAGE_NAME}"
