#!/usr/bin/python3
import struct
import sys
import os

scriptName = sys.argv[0]
if len(sys.argv) != 2:
	print("Usage: %s dirname|filename.[hog|txt]" % scriptName,file=sys.stderr)
	print("Syphon Filter Omega Strain PS2 HOG file unpacker/packer by rajkosto",file=sys.stderr)
	sys.exit(1)

inputFname = sys.argv[1]
inputFnameAndExt = os.path.splitext(inputFname)
inputExt = ''
if len(inputFnameAndExt) > 1:
	inputExt = inputFnameAndExt[1]

openMode = 'rb'
if inputExt.lower() == '.txt':
	openMode = 'r'
elif os.path.isdir(inputFname):
	openMode = ''

inputFile = False
if len(openMode):
	try:
		inputFile = open(inputFname,openMode)
	except IOError:
		print("Error opening main input file: %s" % inputFname,file=sys.stderr)
		sys.exit(2)

def readString(file):
	outBytes = bytearray()
	while True:
		readByte = file.read(1)
		if len(readByte) == 0 or readByte == b'\0':
			break

		outBytes.append(readByte[0])

	return outBytes.decode('latin1')

def writeString(file,text):
	file.write(text.encode('latin1'))
	file.write(b'\0')
	
def alignOffset(offset,alignment):
	ooaNum = offset % alignment
	if ooaNum > 0:
		return offset + alignment - ooaNum
	return offset

fileList = []
if openMode == 'rb': #parse hog
	hdrMtime, hdrNumFiles, hdrListOffset, hdrTextOffset, hdrDataOffset = struct.unpack('<iIIII',inputFile.read(20))

	assert inputFile.tell() == hdrListOffset, "fileList should always be immediately after global header"
	for fileIdx in range(hdrNumFiles+1): #has one extra offset so length of last file can be calculated
		fileOffset = int.from_bytes(inputFile.read(4),'little')
		totalOffset = fileOffset+hdrDataOffset
		fileList.append({ 'offset': totalOffset })
		
	#can calculate lengths now that we have all the offsets
	for fileIdx in range(hdrNumFiles):
		fileList[fileIdx]['length'] = fileList[fileIdx+1]['offset'] - fileList[fileIdx]['offset']
	#remove the last entry since it was only used to calculate offsets
	fileList.pop()

	assert inputFile.tell() == hdrTextOffset, ("text should always be immediately after fileList (tell: %u offset: %u)" % (inputFile.tell(), hdrTextOffset))
	for fileIdx in range(hdrNumFiles):
		fileName = readString(inputFile)
		fileList[fileIdx]['name'] = fileName

	if inputFile.tell() != hdrDataOffset:
		print("file data not immediately following text (tell: %u offset: %u)" % (inputFile.tell(), hdrDataOffset))
		inputFile.seek(hdrDataOffset)
		
	outputDirName = inputFnameAndExt[0]
	if not os.path.isdir(outputDirName):
		os.mkdir(outputDirName)
		
	for fileIdx in range(hdrNumFiles):
		if inputFile.tell() != fileList[fileIdx]['offset']:
			print("file %s not right after previous (tell: %u offset: %u)" % (fileList[fileIdx]['name'], inputFile.tell(), fileList[fileIdx]['offset']))
			inputFile.seek(fileList[fileIdx]['offset'])
		
		outFname = os.path.join(outputDirName,fileList[fileIdx]['name'])
		outFile = False
		try:
			outFile = open(outFname,'wb')
		except IOError:
			print("Error opening output file: %s" % outFname,file=sys.stderr)
			sys.exit(3)
		
		numWritten = 0
		remaining = fileList[fileIdx]['length']		
		while remaining > 0:
			blockSize = 64*1024
			if blockSize > remaining:
				blockSize = remaining
				
			readBytes = inputFile.read(blockSize)
			outFile.write(readBytes)
			numWritten = numWritten + len(readBytes)
			if len(readBytes) < blockSize:
				remaining = 0
			else:
				remaining = remaining - blockSize
		
		outFile.close()
		os.utime(outFname,times=(hdrMtime,hdrMtime))
		assert numWritten == fileList[fileIdx]['length'], "input file must have enough bytes to hold inner file data"
	
	outputTxtName = outputDirName
	if outputTxtName.endswith('\\') or outputTxtName.endswith('/'):
		outputTxtName = outputTxtName[:-1]
	
	inputFile.close()
	outputTxtName = outputTxtName + '.txt'
	outTxtFile = False
	try:
		outTxtFile = open(outputTxtName,'w',encoding='latin1')
	except IOError:
		print("Error opening output txt file: %s" % outTxtFile,file=sys.stderr)
		sys.exit(4)
	
	for fileIdx in range(hdrNumFiles):
		outTxtFile.write(fileList[fileIdx]['name'])
		outTxtFile.write('\n')
		
	outTxtFile.close()
	os.utime(outputTxtName,times=(hdrMtime,hdrMtime))
else: #create hog
	if openMode == 'r': #read files from txt
		lines = inputFile.readlines()
		inputFile.close()
		for line in lines:
			if line.endswith('\n'):
				line = line[:-1]
				
			if len(line) < 1:
				continue
				
			fileList.append({ 'name': line })
	else: #read files from dir
		fnames = os.listdir(inputFname)
		for fname in fnames:
			if len(fname) < 1 or os.path.isdir(os.path.join(inputFname,fname)):
				continue
			
			fileList.append({ 'name': fname })
			
	inputDirName = inputFnameAndExt[0]
	hdrMtime = 0
	for fileEntry in fileList:
		fileEntry['path'] = os.path.join(inputDirName,fileEntry['name'])
		try:
			fileEntry['length'] = int(os.path.getsize(fileEntry['path']))
			fileEntry['mtime'] = int(os.path.getmtime(fileEntry['path']))
			if fileEntry['mtime'] > hdrMtime:
				hdrMtime = fileEntry['mtime']
				
			fileEntry['file'] = open(fileEntry['path'],'rb')
		except IOError:
			print("Error opening input data file: %s" % fileEntry['path'],file=sys.stderr)
			sys.exit(5)
		
	outputHogName = inputDirName
	if outputHogName.endswith('\\') or outputHogName.endswith('/'):
		outputHogName = outputHogName[:-1]
	
	outputHogName = outputHogName + '.HOG'
	outHogFile = False
	try:
		outHogFile = open(outputHogName,'wb')
	except IOError:
		print("Error opening output hog file: %s" % outputHogName,file=sys.stderr)
		sys.exit(6)
	
	hdrNumFiles = int(len(fileList))
	outHogFile.write(b'\0' * 20) #global header space
	hdrListOffset = int(outHogFile.tell())
	
	numOffsets = hdrNumFiles+1
	outHogFile.write(b'\0' * (numOffsets * 4)) #file offset space
	hdrTextOffset = int(outHogFile.tell())
	
	for fileEntry in fileList:
		writeString(outHogFile,fileEntry['name'])
	
	hdrDataOffset = int(outHogFile.tell())
	for fileIdx in range(hdrNumFiles):
		dataAlignment = 16
		if fileList[fileIdx]['name'].upper().endswith('.HOG'):
			dataAlignment = 2048
			
		outPos = int(outHogFile.tell())
		outAlignedPos = alignOffset(outPos,dataAlignment)
		if outAlignedPos > outPos:
			outHogFile.write(b'\0' * (outAlignedPos-outPos)) #put in the before file alignment bytes
		
		assert outHogFile.tell() == outAlignedPos, "should be aligned now"
		if fileIdx == 0:
			hdrDataOffset = outAlignedPos
			
		fileList[fileIdx]['offset'] = outAlignedPos - hdrDataOffset
		remaining = fileList[fileIdx]['length']
		numWritten = 0
		while remaining > 0:
			blockSize = 64*1024
			if blockSize > remaining:
				blockSize = remaining
				
			readBytes = fileList[fileIdx]['file'].read(blockSize)
			outHogFile.write(readBytes)
			numWritten = numWritten + len(readBytes)
			if len(readBytes) < blockSize:
				remaining = 0
			else:
				remaining = remaining - blockSize
		
		fileList[fileIdx]['file'].close()
		assert numWritten == fileList[fileIdx]['length'], "should have written entire input file into hog"
		if fileIdx == len(fileList)-1: #need to add the extra offset from the last one's end
			nextFileOffs = int(outHogFile.tell()-hdrDataOffset)
			fileList.append({ 'offset': nextFileOffs })
	
	endingPos = outHogFile.tell()	
	assert endingPos == fileList[-1]['offset'] + hdrDataOffset, "should be at end of hog file"
	endingPosAligned = alignOffset(endingPos,2048) #hog files must have size multiple of 2048
	if endingPosAligned > endingPos:
		outHogFile.write(b'\0' * (endingPosAligned-endingPos)) #put in the end alignment bytes
	
	outHogFile.seek(0)
	outHogFile.write(struct.pack('<iIIII',hdrMtime,hdrNumFiles,hdrListOffset,hdrTextOffset,hdrDataOffset))
	assert outHogFile.tell() == hdrListOffset, "should be at hog list offset"
	
	for fileEntry in fileList:
		outHogFile.write(struct.pack('<I',fileEntry['offset']))
		
	assert outHogFile.tell() == hdrTextOffset, "should be at hog text offset"
	outHogFile.close()
	os.utime(outputHogName,times=(hdrMtime,hdrMtime))