#Author: Seth Barnard
import pprint
import sys

import numpy

from nupic.data.fieldmeta import FieldMetaType
from nupic.encoders.base import Encoder
from nupic.data import SENTINEL_VALUE_FOR_MISSING_DATA
from nupic.bindings.math import Random as NupicRandom

class RandomDistributedCategoryEncoder(Encoder):

  def __init__(self, w=21, n=400, name=None, seed=42, verbosity=0):
    """Constructor

    @param w Number of bits to set in output. w must be odd to avoid centering
                    problems.  w must be large enough that spatial pooler
                    columns will have a sufficiently large overlap to avoid
                    false matches. A value of w=21 is typical.

    @param n Number of bits in the representation (must be > w). n must be
                    large enough such that there is enough room to select
                    new representations as the range grows. With w=21 a value
                    of n=400 is typical. The class enforces n > 6*w.

    @param name An optional string which will become part of the description.

    @param seed The seed used for numpy's random number generator. If set to -1
                    the generator will be initialized without a fixed seed.

    @param verbosity An integer controlling the level of debugging output. A
                    value of 0 implies no output. verbosity=1 may lead to
                    one-time printouts during construction, serialization or
                    deserialization. verbosity=2 may lead to some output per
                    encode operation. verbosity>2 may lead to significantly
                    more output.
    """
    # Validate inputs
    if (w <= 0) or (w%2 == 0):
      raise ValueError("w must be an odd positive integer")
 
    if (n <= 6*w) or (not isinstance(n, int)):
      raise ValueError("n must be an int strictly greater than 6*w. For "
                       "good results we recommend n be strictly greater "
                       "than 11*w")

    self.encoders = None
    self.verbosity = verbosity
    self.w = w
    self.n = n
    self.overlapLevel = 0
    self.bucketIndexMap = {"NOT_DEFINED":0}
    self.currOverlapLevel = 0;
    
    # initialize the random number generators
    self._seed(seed)

    self.bucketMap = {}
    self.bitToCatIndexList = {k: [] for k in xrange(self.n)}

    # A name used for debug printouts
    if name is not None:
      self.name = name
    else:
      self.name = "RDCE"

    if self.verbosity > 0:
      self.dump()

  def __setstate__(self, state):
    self.__dict__.update(state)

    # Initialize self.random as an instance of NupicRandom derived from the
    # previous numpy random state
    randomState = state["random"]
    if isinstance(randomState, numpy.random.mtrand.RandomState):
      self.random = NupicRandom(randomState.randint(sys.maxint))


  def getScalars(self, input):
    """ See method description in base.py """
    if input == SENTINEL_VALUE_FOR_MISSING_DATA:
      return numpy.array([0])
        
      index = self.bucketIndexMap.get(input, None)
    if index is None:
      index = 0

    return numpy.array([index])
  
  def _seed(self, seed=-1):
    """
    Initialize the random seed
    """
    if seed != -1:
      self.random = NupicRandom(seed)
    else:
      self.random = NupicRandom()


  def getDecoderOutputFieldTypes(self):
    """ See method description in base.py """
    return (FieldMetaType.float, )


  def getWidth(self):
    """ See method description in base.py """
    return self.n


  def getDescription(self):
    return [(self.name, 0)]


  def getBucketIndices(self, x):
    """ See method description in base.py """

    if x in self.bucketIndexMap:
      bucketIdx = self.bucketIndexMap[x]
    else:
      if self.currOverlapLevel>=self.w:
        bucketIdx = 0
      else:
        bucketIdx = max(self.bucketIndexMap.values())+1
        if self.verbosity >= 2:
          print "Index is not found for ", x, "Created new index", bucketIdx
        self.bucketIndexMap[x] = bucketIdx

    return [bucketIdx]


  def mapBucketIndexToNonZeroBits(self, index):
    """
    Given a bucket index, return the list of non-zero bits. If the bucket
    index does not exist, it is created.
    """
    if not self.bucketMap.has_key(index):
      if self.verbosity >= 2:
        print "Adding additional bucket to handle index=", index
      self._createBucket(index)
    return self.bucketMap[index]


  def encodeIntoArray(self, x, output):
    """ See method description in base.py """

    if x is not None and not isinstance(x, str):
      raise TypeError(
          "Expected a string input but got input of type %s" % type(x))

    # Get the bucket index to use
    bucketIdx = self.getBucketIndices(x)[0]

    if self.verbosity >=2:
      print "Category to encode=", x
      print "Category bucket index=", bucketIdx
    # None is returned for missing value in which case we return all 0's.
    output[0:self.n] = 0
    if bucketIdx is not None:
      output[self.mapBucketIndexToNonZeroBits(bucketIdx)] = 1


  def _createBucket(self, index):
    self.bucketMap[index] = self.createNewRepresentation(index)
  
  def createNewRepresentation(self, index):
    currUsageCountMap = {}
    """Setup new sdr"""
    newRepresentation = [None]*self.w
    
    """Find w bits to use in new sdr"""
    for x in xrange(self.w):
      valid = False
      while not valid:
        """Look for lowest used bit first"""
        currBit, currLvl = self.findFirstLowestBit()
        count = 0
        """Validate that chosen bit satisfies overlap restrictions"""
        valid = self.chosenBitIsOk(currBit, currUsageCountMap)
        
        """If invalid, iterate through rest of bits with current bit usage count"""
        while not valid and count<self.n:
          count += 1
          currBit = self.findNextEqualBit(currBit, currLvl)
          """If the end of n bits is reached, increment usage level and start back at beginning
            otherwise validate chosen bit"""
          if currBit is -1:
            currBit = 0
            currLvl += 1
          else:
            valid = self.chosenBitIsOk(currBit, currUsageCountMap)
            
        """If all bits have been searched and no valid bits found,
          increment overlap level.  Next round of chosen bits will be validated 
          with incremented overlap count"""
        if not valid and count>=self.n:
          self.currOverlapLevel +=1
          print self.currOverlapLevel
          print len(self.bucketIndexMap)-1
      
      """Once a valid bit is found, add it to sdr and add tracking info"""
      newRepresentation[x]=currBit
      self.bitToCatIndexList[currBit].append(index)
    return newRepresentation
  
  def findNextEqualBit(self, index, val):
    nextBit = -1
    for x in xrange(index+1, self.n):
      if(len(self.bitToCatIndexList[x])==val):
        nextBit = x
        break
    return nextBit

  def chosenBitIsOk(self, index, currUsageCountMap):
    valid = True
    """Count overlaps with other sdrs that use this bit"""
    for c in self.bitToCatIndexList[index]:
      if c in currUsageCountMap and currUsageCountMap[c]+1>self.currOverlapLevel:
        valid = False
        break
    
    """If a valid bit, add tracking info to be used while searching for other
      bits in this sdr"""
    if valid:
      for c in self.bitToCatIndexList[index]:
        if c in currUsageCountMap:
          currUsageCountMap[c] = currUsageCountMap[c]+1
        else:
          currUsageCountMap[c] = 1
    return valid

  def findFirstLowestBit(self, exclusionVal=0):
    currMin = len(self.bitToCatIndexList[0])
    currKey = 0
    for x in xrange(self.n):
      if len(self.bitToCatIndexList[x])<currMin and len(self.bitToCatIndexList[x])>=exclusionVal:
        currMin = len(self.bitToCatIndexList[x])
        currKey = x
    return (currKey, currMin)
  
  def dump(self):
    print "RandomDistributedCategoryEncoder:"
    print "  w:          %d" % self.w
    print "  n:          %d" % self.getWidth()
    print "  name:       %s" % self.name
    if self.verbosity > 2:
      print "  All buckets:     "
      pprint.pprint(self.bucketMap)

  @classmethod
  def read(cls, proto):
    encoder = object.__new__(cls)
    encoder.w = proto.w
    encoder.n = proto.n
    encoder.name = proto.name
    encoder.random = NupicRandom()
    encoder.random.read(proto.random)
    encoder.verbosity = proto.verbosity
    encoder.encoders = None
    encoder.bucketMap = {x.key: numpy.array(x.value, dtype=numpy.uint32)
                         for x in proto.bucketMap}

    return encoder

  def getCurrentOverlapLevel(self):
    return self.currOverlapLevel

  def write(self, proto):
    proto.w = self.w
    proto.n = self.n
    proto.name = self.name
    self.random.write(proto.random)
    proto.verbosity = self.verbosity
    proto.bucketMap = [{"key": key, "value": value.tolist()}
                       for key, value in self.bucketMap.items()]
