# Based on bdj-sdk samples/helloworld (GPLv3, John Törnblom). Built via disc/build.sh.
DISC_LABEL := Biblioteca

BDJSDK_HOME ?= $(abspath ../..)
BDSIGNER    := $(BDJSDK_HOME)/host/bin/bdsigner
MAKEFS      := $(BDJSDK_HOME)/host/bin/makefs
JAVA8_HOME  ?= $(BDJSDK_HOME)/host/jdk8
JAVAC       := $(JAVA8_HOME)/bin/javac
JAVA        := $(JAVA8_HOME)/bin/java
JAR         := $(JAVA8_HOME)/bin/jar
export JAVA8_HOME

CLASSPATH := $(BDJSDK_HOME)/target/lib/enhanced-stubs.zip
SOURCES   := $(shell find src -name '*.java' ! -name '*Test.java')
JFLAGS    := -Xlint:-options -source 1.3 -target 1.3 -encoding UTF-8

TMPL_DIRS  := $(shell find $(BDJSDK_HOME)/resources/AVCHD/ -type d)
TMPL_FILES := $(shell find $(BDJSDK_HOME)/resources/AVCHD/ -type f)
DISC_DIRS  := $(patsubst $(BDJSDK_HOME)/resources/AVCHD%,discdir%,$(TMPL_DIRS)) discdir/BDMV/JAR
DISC_FILES := $(patsubst $(BDJSDK_HOME)/resources/AVCHD%,discdir%,$(TMPL_FILES)) discdir/BDMV/JAR/00000.jar

all: $(DISC_LABEL).iso

test:
	rm -rf testout && mkdir testout
	$(JAVAC) $(JFLAGS) -d testout src/org/biblio/Proto.java src/org/biblio/ProtoTest.java
	$(JAVA) -cp testout org.biblio.ProtoTest

discdir:
	mkdir -p $(DISC_DIRS)

# The template BDJO starts org.homebrew.MyXlet, so that class is our entry point.
discdir/BDMV/JAR/00000.jar: discdir $(SOURCES)
	rm -rf classes && mkdir classes
	$(JAVAC) $(JFLAGS) -cp $(CLASSPATH) -d classes $(SOURCES)
	cp src/org/homebrew/bluray.MyXlet.perm classes/org/homebrew/
	$(JAR) cf $@ -C classes .
	$(BDSIGNER) -keystore $(BDJSDK_HOME)/resources/sig.ks $@

discdir/%: discdir
	cp $(BDJSDK_HOME)/resources/AVCHD/$* $@

$(DISC_LABEL).iso: $(DISC_FILES)
	$(MAKEFS) -m 16m -t udf -o T=bdre,v=2.50,L=$(DISC_LABEL) $@ discdir

clean:
	rm -rf META-INF classes testout discdir $(DISC_LABEL).iso
