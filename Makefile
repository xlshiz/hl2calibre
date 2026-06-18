PLUGIN_NAME   := hl2calibre
OUTPUT        := $(PLUGIN_NAME).zip

# 打包所需的源文件
PY_SRCS      := __init__.py action.py mrexpt_parser.py book_matcher.py \
                cfi_encoder.py converter.py importer.py ui.py
TXTS         := plugin-import-name-$(PLUGIN_NAME).txt
IMAGES       := $(wildcard images/*)
ALL_SRCS     := $(PY_SRCS) $(TXTS) $(IMAGES)

.PHONY: all package test clean

all: package

package: $(OUTPUT)

$(OUTPUT): $(ALL_SRCS)
	rm -f $@
	python3 -c "import zipfile;zf=zipfile.ZipFile('$@','w',zipfile.ZIP_DEFLATED);[zf.write(f,f) for f in '$(PY_SRCS) $(TXTS)'.split()];[zf.write(i,i) for i in '$(IMAGES)'.split()];zf.close()"
	@echo "打包完成: $@"

test:
	python -m pytest tests/ -v --rootdir=tests

clean:
	rm -f $(OUTPUT)
	rm -rf __pycache__ */__pycache__ .pytest_cache
