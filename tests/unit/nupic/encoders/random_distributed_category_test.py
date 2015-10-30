#!/usr/bin/env python
#Author: Seth Barnard
#----------------------------------------
from cStringIO import StringIO
import sys
import tempfile
import unittest2 as unittest
import numpy

from nupic.encoders.base import defaultDtype
from nupic.data import SENTINEL_VALUE_FOR_MISSING_DATA
from nupic.data.fieldmeta import FieldMetaType
from nupic.support.unittesthelpers.algorithm_test_helpers import getSeed
from nupic.encoders.random_distributed_category import (
  RandomDistributedCategoryEncoder
)



def computeOverlap(x, y):
  return (x & y).sum()



def validateEncoder(encoder, subsampling):
  """
  Given an encoder, calculate overlaps statistics and ensure everything is ok.
  We don't check every possible combination for speed reasons.
  """
  for i in range(encoder.minIndex, encoder.maxIndex+1, 1):
    for j in range(i+1, encoder.maxIndex+1, subsampling):
      if not encoder._overlapOK(i, j):
        return False

  return True

class RandomDistributedCategoryEncoderTest(unittest.TestCase):

  def testEncoding(self):
    # Initialize with non-default parameters and encode with a number close to
    # the offset
    width = 11
    bits = 200
    encoder = RandomDistributedCategoryEncoder(name="encoder", w=width, n=bits)
    count=1
    for x in xrange(count): 
      e0 = encoder.encode("T"+str(x))

      self.assertEqual(e0.sum(), width, "Number of on bits is incorrect")
      self.assertEqual(e0.size, bits, "Width of the vector is incorrect")


  def testOverlap(self):
    # Initialize with non-default parameters and encode with a number close to
    # the offset
    encoder = RandomDistributedCategoryEncoder(name="encoder", w=21, n=400, )
    results = []
    numCatsToEncode = 10000
    for x in xrange(numCatsToEncode):
      if x%50==0:
        print x, " SDRs have been encoded."
      results.append(encoder.encode(str(x)))
    
    i = 0
    for sdr in results:
      if i%50==0:
        print i, " records have been overlap and duplicate checked."
      count = 0
      for comp in results:
        if (comp==sdr).all():
          count = count+1
        else:
          if(computeOverlap(comp, sdr)>encoder.getCurrentOverlapLevel()):
            print comp
            print sdr
            print computeOverlap(comp, sdr)
          self.assertTrue(computeOverlap(comp, sdr)<=encoder.getCurrentOverlapLevel(), "Sdrs have too much overlap")
      self.assertEqual(count, 1, "Two sdrs were created with the same bits")
      i += 1

    print "Global overlap level after encoding is: ", encoder.getCurrentOverlapLevel()
    
    for x in xrange(1, numCatsToEncode+1):
      count = 0
      for val in encoder.bitToCatIndexList.values():
        count += val.count(x)
      self.assertTrue(count==encoder.w, "Wait a sec. The SDR at this index: "+str(x)+" doesn't have the correct number of bits used: "+str(count))
    print "Active bit count and tracking is OK!"

if __name__ == "__main__":
  unittest.main()
