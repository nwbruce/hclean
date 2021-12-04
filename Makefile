
build:
	$(eval TEMPF:=$(shell /usr/bin/mktemp).cpp)
	cp testfile.cpp $(TEMPF)
	./include_cleaner.py $(TEMPF)
	-git diff -- testfile.cpp $(TEMPF)
	rm *.o $(TEMPF)