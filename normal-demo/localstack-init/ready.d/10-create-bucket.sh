#!/bin/bash
set -euo pipefail

awslocal s3api create-bucket --bucket image-bank || true
awslocal s3api put-object --bucket image-bank --key _config/super_indices.json --body /etc/localstack/init/ready.d/super.json
