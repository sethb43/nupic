@0xa4f79e07a0df410d;

using import "../bindings/proto/RandomProto.capnp".RandomProto;

# Next ID: 10
struct RandomDistributedCategoryEncoderProto {
  w @1 :UInt32;
  n @2 :UInt32;
  name @3 :Text;
  random @5 :RandomProto;
  verbosity @6 :UInt8;
  bucketMap @9 :List(BucketMapping);

  # Next ID: 2
  struct BucketMapping {
    key @0 :UInt32;
    value @1 :List(UInt32);
  }

}
