PREFIX := $(HOME)/.local
LIBDIR := $(PREFIX)/lib/omarchy-export
BINDIR := $(PREFIX)/bin

.PHONY: install uninstall clean test

install:
	mkdir -p $(LIBDIR) $(BINDIR)
	cp -r omarchy_export $(LIBDIR)/
	install -m 755 bin/omarchy-export $(BINDIR)/omarchy-export
	@echo "Installed to $(BINDIR)/omarchy-export"

uninstall:
	rm -rf $(LIBDIR)
	rm -f $(BINDIR)/omarchy-export

clean:
	find . -name __pycache__ -type d -exec rm -rf {} +

test: install
	omarchy-export --version
