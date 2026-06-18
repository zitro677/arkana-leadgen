#!/usr/bin/env bash
cd /root/arkana_leadgen || exit 1
/root/arkana_leadgen/.venv/bin/python lead_gen.py --ciudad Bogotá >> /root/arkana_leadgen/cron.log 2>&1
