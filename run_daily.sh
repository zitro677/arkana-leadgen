#!/usr/bin/env bash
# Corre el grupo del día (rotación A/B), ambas ciudades: Bogotá + Nashville TN.
cd /root/arkana_leadgen || exit 1
/root/arkana_leadgen/.venv/bin/python lead_gen.py >> /root/arkana_leadgen/cron.log 2>&1
