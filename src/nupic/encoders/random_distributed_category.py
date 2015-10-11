# ----------------------------------------------------------------------
# Numenta Platform for Intelligent Computing (NuPIC)
# Copyright (C) 2013-2015, Numenta, Inc.  Unless you have an agreement
# with Numenta, Inc., for a separate license for this software code, the
# following terms and conditions apply:
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see http://www.gnu.org/licenses.
#
# http://numenta.org/licenses/
# ----------------------------------------------------------------------

import pprint
import sys

import numpy

from nupic.data.fieldmeta import FieldMetaType
from nupic.encoders.base import Encoder
from nupic.bindings.math import Random as NupicRandom


class RandomDistributedCategoryEncoder(Encoder):

  def __init__(self, w=21, n=400, o=5, name=None, seed=42, verbosity=0):
    """Constructor

    @param w Number of bits to set in output. w must be odd to avoid centering
                    problems.  w must be large enough that spatial pooler
                    columns will have a sufficiently large overlap to avoid
                    false matches. A value of w=21 is typical.

    @param n Number of bits in the representation (must be > w). n must be
                    large enough such that there is enough room to select
                    new representations as the range grows. With w=21 a value
                    of n=400 is typical. The class enforces n > 6*w.
                    
    @param o Number of bits that are allowed to overlap with any other single 
                    representation.  Note that this parameter only refers to 
                    a specific representation, more than one(or many) 
                    representations can overlap by this value.

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
      
    if (not isinstance(o, int)) or (o < 0):
      raise ValueError("O must be a positive integer.")
    
    if (o < w/4):
      raise ValueError("O must be greater than W/4.")
    
    if (o < w/3):
      print "WARNING.  WARNING.  WARNING. WARNING."
      print "With such a small O value, you are asking for trouble.  New categories"
      print " will require more and more CPU time as the number of categories increase."

    self.encoders = None
    self.verbosity = verbosity
    self.w = w
    self.n = n
    self.overlapLevel = 0
    self.maxOverlap = o
    self.bucketIndexMap = {"NOT_DEFINED":0}

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
      bucketIdx = max(self.bucketIndexMap.values())+1
      if self.verbosity >= 2:
        print "Index is not found for ", x, "Created new index", bucketIdx
      self.bucketIndexMap[x] = bucketIdx

    return [bucketIdx]


  def mapBucketIndexToNonZeroBits(self, index):
    """
    Given a bucket index, return the list of non-zero bits. If the bucket
    index does not exist, it is created. If the index falls outside our range
    we clip it.
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

  #=============================================================================
  # def createNewRepresentation(self, index):
  #   newRepresentation = [None]*self.w
  #   bitCatUsageCountMap = {}
  #   for x in xrange(self.w):
  #     
  #     newRepresentation[x] = self.random.getUInt32(self.n)
  #     while not self.chosenBuckitIndexIsOk(newRepresentation[x], bitCatUsageCountMap):
  #       newRepresentation[x] = self.random.getUInt32(self.n)
  #     
  #     self.bitToCatIndexList[newRepresentation[x]].append(index)
  #     
  #   return newRepresentation
  # 
  # def chosenBuckitIndexIsOk(self, bucketIndex, bitCatUsageCountMap):
  #   for c in self.bitToCatIndexList[bucketIndex]:
  #     if c in bitCatUsageCountMap:
  #       if bitCatUsageCountMap[c]+1 > self.maxOverlap:
  #         return False
  #       else: 
  #         bitCatUsageCountMap[c] = bitCatUsageCountMap[c]+1
  #     else:
  #       bitCatUsageCountMap[c] = 1
  #   return True
  #=============================================================================
  
  def createNewRepresentation(self, index):
    newRepresentation = [None]*self.w

      
    return newRepresentation
  
  def getFirstMinUsedIndexCount(self, dictList):
    minUsedIndex = 0
    minUsedCount = self.maxOverlap+1
    for k in dictList.keys:
      if(len(dictList[k])<minUsedCount):
        minUsedCount = len(dictList[k])
        minUsedIndex = k
    return (minUsedIndex, minUsedCount)

  def dump(self):
    print "RandomDistributedCategoryEncoder:"
    print "  w:          %d" % self.w
    print "  n:          %d" % self.getWidth()
    print "  name:       %s" % self.name
    print "  s:          %s" % self.maxOverlap
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


  def write(self, proto):
    proto.w = self.w
    proto.n = self.n
    proto.name = self.name
    self.random.write(proto.random)
    proto.verbosity = self.verbosity
    proto.bucketMap = [{"key": key, "value": value.tolist()}
                       for key, value in self.bucketMap.items()]
