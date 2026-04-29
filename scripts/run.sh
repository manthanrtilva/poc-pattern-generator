#!/bin/bash

set -eou pipefail
 
# cleanup on exit
on_exit() {
	pkill -9 -f pattern-generator || true
	pkill -9 -f vite || true
	pkill -9 -f concurrently || true
}
trap on_exit EXIT

cd /workspaces/poc-pattern-generator && npm run dev
