# Makefile — owned root. YOU own this file; racecar never rewrites it.
#
# The canonical racecar build (every standard target + the shape-derived
# variables) lives in racecar.mk, which racecar regenerates for this repo's
# detected shape on `make sync`. `make help` lists every target from both files.
#
# Customize here, never in racecar.mk:
#   - add a project-specific target below the include;
#   - override a canonical recipe by redefining it below (last definition wins);
#   - override a shape variable by setting it with := ABOVE the include
#     (racecar.mk assigns shape vars with ?=, so an earlier := wins).

include racecar.mk

# --- project-specific targets (examples; delete what you do not use) ---
# system-deps: ## install system dependencies (overrides racecar.mk's default)
# 	$(PYTHON) -m playwright install chromium
#
# bench: ## run the domain benchmark suite
# 	$(PYTHON) -m mypkg.bench
