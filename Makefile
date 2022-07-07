
CC=g++ -c -x c++-header -I test/ -o /dev/null

build:
	rm -f log.txt
	./hclean.py -j 8 \
		-c "$(CC) {}" \
		-l log.txt \
		-I test/ \
		-S /Library/Developer/CommandLineTools/usr/lib/clang/13.0.0/include \
 		-S /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/usr/include \
 		-S /Library/Developer/CommandLineTools/usr/include \
 		-S /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/System/Library/Frameworks \
		-S /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/usr/include/c++/v1 \
		test/*.cpp

cc:
	$(CC) test/collector.h
	$(CC) test/collector_util.h
	$(CC) test/collector.cpp
	$(CC) test/main.cpp

#	$(eval TEMPF:=$(shell /usr/bin/mktemp).cpp)
#	cp testfile.cpp $(TEMPF)


# "g++ -c" $(TEMPF) 
#	-git diff -- testfile.cpp $(TEMPF)
#	rm *.o $(TEMPF)