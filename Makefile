
build:
	rm -f log.txt
	./hclean.py -j 2 \
		-I test/ \
		-isystem /Library/Developer/CommandLineTools/usr/lib/clang/13.0.0/include \
 		-isystem /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/usr/include \
 		-isystem /Library/Developer/CommandLineTools/usr/include \
 		-isystem /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/System/Library/Frameworks \
		-isystem /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/usr/include/c++/v1 \
		test/*.cpp

CC=g++ -c -x c++-header -I test/ -o /dev/null
cc:
	$(CC) test/collector.h
	$(CC) test/collector_util.h
	$(CC) test/collector.cpp

#	$(eval TEMPF:=$(shell /usr/bin/mktemp).cpp)
#	cp testfile.cpp $(TEMPF)


# "g++ -c" $(TEMPF) 
#	-git diff -- testfile.cpp $(TEMPF)
#	rm *.o $(TEMPF)