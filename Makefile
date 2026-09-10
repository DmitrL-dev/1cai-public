.PHONY: release-notes release-tag release-push

release-notes:
	@test -n "$(VERSION)" || (echo "VERSION is required"; exit 1)
	python scripts/release/create_release.py --version "$(VERSION)"

release-tag:
	@test -n "$(VERSION)" || (echo "VERSION is required"; exit 1)
	python scripts/release/create_release.py --version "$(VERSION)" --tag

release-push:
	@test -n "$(VERSION)" -a -n "$(REMOTE)" || (echo "VERSION and REMOTE are required"; exit 1)
	python scripts/release/create_release.py --version "$(VERSION)" --push --remote "$(REMOTE)"
