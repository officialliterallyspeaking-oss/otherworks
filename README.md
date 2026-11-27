# Nigerian constitutional research documents

**[Download the Constitution (PDF, 8.2 MiB)](https://github.com/officialliterallyspeaking-oss/otherworks/raw/refs/heads/main/research/pdfs/Nigeria-Constitution-1999-First-to-Fifth-Alterations-PLAC-2024-Reprint.pdf)** · **[Download any of the 23 PDFs](research/pdfs/README.md)** · **[Get the entire collection as a ZIP](https://github.com/officialliterallyspeaking-oss/otherworks/archive/refs/heads/main.zip)**

The PDFs are ordinary files in [`research/pdfs/`](research/pdfs/). Their filenames identify the jurisdiction, document and year or edition. The ZIP contains that directory and the 74 other sources. No special software, live preview or Git LFS is needed to download the files.

The Constitution is PLAC’s edition through the Fifth Alteration, reprinted in 2024, **not** a government-certified consolidation through 2026. The [reader’s guide](research/README.md) explains coverage and gaps. The [97-file manifest](research/manifest.csv) records each file’s path, provenance and SHA-256; the [external register](research/originals.csv) lists additional sources not necessarily held here.

In a checkout, `python3 research/verify-holdings.py` verifies all 97 source files. `python3 research/library.py` opens the local download library on port 8000 and assembles the five topic ZIPs; `python3 research/build_archives.py` also assembles them without starting a server. Python 3.8+; no third-party packages.
