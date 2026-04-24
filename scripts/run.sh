#!/bin/bash

set -eou pipefail

pkill -9 -f pattern-generator || true
pkill -9 -f vite || true
pkill -9 -f concurrently || true
cd /workspaces/poc-pattern-generator && npm run dev
