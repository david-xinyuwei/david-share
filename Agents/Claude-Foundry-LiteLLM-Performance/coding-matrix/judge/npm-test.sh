#!/bin/bash
# Same steps as Aider's benchmark/npm-test.sh.
set -e

[ ! -e node_modules ] && ln -s /npm-install/node_modules .
[ ! -e package-lock.json ] && ln -s /npm-install/package-lock.json .

sed -i 's/\bxtest(/test(/g' *.spec.js
npm run test
