#!/bin/sh
set -eu
umask 077
exec python -m hads_next.addon_server
