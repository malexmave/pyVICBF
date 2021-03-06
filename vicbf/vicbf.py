# -*- encoding: utf-8 -*-
"""This module implements a Variable-Increment Counting Bloom Filter.

The VI-CBF was originally proposed by Rottenstreich et al. in their paper
"The Variable-Increment Counting Bloom Filter", IEEE INFOCOM 2012,

    http://www.cs.technion.ac.il/~ykanizo/papers/tr11-05_variable.pdf

The VI-CBF is an improvement over the regular CBF, as it provides a lower
False Positive Rate with the same number of bits. It works by incrementing
the counters of the bloom filter with variable values when inserting
elements, as opposed to simply incrementing by one. This allows more
accurate statements about the likelyhood that a certain element is in
a certain filter.

For more details, check the original paper (linked above).

This implementation is built for readability, not efficiency. If you need an
efficient VICBF implementation, build your own :)
"""
import hashlib
from math import factorial, log, ceil
from bitstring import pack, ReadError


class VICBF():
    """A basic VICBF implementation"""

    MODE_DUMP_ALL  = 0
    MODE_SELECTIVE = 1

    def __init__(self, slots, hash_functions, vibase=4):
        """Counstructor for the VICBF.

        Attributes:
            slots -- The number of slots (counters) the bloom filter should use.
            called "m" in the paper.

            hash_functions -- The number of hash functions to use. Called k in the
            paper.

            vibase -- The base for the variable-increment lookup table. Called L
            in the paper. A good value seems to be 4 or 8, according to the paper.
            Must be one of 2, 4, 8, 16.
        """
        # TODO See if I can change the parameter to state a desired FPR
        if slots < 1:
            raise ValueError("slots must be >=1")
        if hash_functions < 1:
            raise ValueError("hash_functions must be >=1")
        if vibase not in (2, 4, 8, 16):
            raise ValueError("vibase must be one of 2, 4, 8, 16")
        self.BF = {}
        self.slots = slots
        self.entries = 0
        self.hash_functions = hash_functions
        self.L = vibase
        # Number of bits per counter
        self.bpc = 8
        # Number of bits per counter index - will be used during serialization
        self.bpi = ceil(log(self.slots, 2) / 8) * 8

    def insert(self, key):
        """Insert a value into the bloom filter

        Arguments:
            key -- the key to insert.
        """
        if key is None:
            raise ValueError("Key cannot be None")
        for i in range(self.hash_functions):
            # Compute the slot index and increment value
            slot_index, increment = self._calculate_slot_and_increment(key, i)
            # Perform the increment in the bloom filter
            try:
                if self.BF[slot_index] + increment >= 2 ** self.bpc - 1:
                    self.BF[slot_index] = 2 ** self.bpc - 1
                else:
                    self.BF[slot_index] += increment
            except KeyError:
                self.BF[slot_index] = increment
        self.entries += 1

    def remove(self, key):
        """Remove a value from the bloom filter

        Arguments:
            key -- the key to remove.
        """
        if key is None:
            raise ValueError("Key cannot be None")
        ops = []
        for i in range(self.hash_functions):
            # Compute the slot and increment values
            slot_index, decrement = self._calculate_slot_and_increment(key, i)
            # Perform the decrement in the bloom filter
            try:
                if self.BF[slot_index] == 2 ** self.bpc - 1:
                    # If the counter experienced an overflow, we cannot modify
                    # it, as that may lead to false negatives in the long run.
                    # Leave it as it is and continue on
                    continue
                elif self.BF[slot_index] - decrement < 0:
                    # After the decrement, the counter would be negative.
                    # This should be impossible and indicates incorrect usage.
                    raise ValueError("Trying to remove entry not in VICBF")
                elif self.BF[slot_index] - decrement == 0:
                    # After the decrement, the counter is zero. Remove the
                    # entry from the hashtable to save space.
                    # We have to defer this operation, because it is not yet
                    # clear if the key is actually in the bloom filter. Thus,
                    # the operation will only be executed if no error occurs
                    # later in the processing
                    ops += [('del', slot_index, 0)]
                else:
                    # After the decrement, the counter will still be positive.
                    # Perform the decrement
                    # We have to defer this operation, because it is not yet
                    # clear if the key is actually in the bloom filter. Thus,
                    # the operation will only be executed if no error occurs
                    # later in the processing
                    ops += [('decr', slot_index, decrement)]
            except KeyError:
                # A KeyError should not occur if the item is in the VICBF, so
                # this indicates incorrect usage. Raise an exception
                raise ValueError("Trying to remove entry not in VICBF")
        for op, idx, decr in ops:
            if op == 'del':
                del self.BF[idx]
            elif op == 'decr':
                self.BF[idx] -= decr
        self.entries -= 1

    def query(self, key):
        """Query the bloom filter for a specific key

        Arguments:
            key -- The key that should be queried

        Returns: True if the key may be in the bloom filter, False if it is
            definitely NOT in the bloom filter.
        """
        if key is None:
            raise ValueError("Key cannot be None")
        for i in range(self.hash_functions):
            # Compute the slot and increment values
            slot_index, decrement = self._calculate_slot_and_increment(key, i)
            # Perform the decrement in the bloom filter
            try:
                decr_value = self.BF[slot_index] - decrement
                if decr_value < 0:
                    # The slot value minus the decrement is lower than zero.
                    # This indicates that the key has not been inserted into
                    # this VICBF
                    return False
                elif decr_value > 0 and decr_value < self.L:
                    # The decremented value is larger than zero, but smaller
                    # than L. This value is not plausible if the key has been
                    # inserted into this VICBF, as decr_value would have to be
                    # either zero or at least L after the decrement.
                    # Thus, the key has not been inserted into the VICBF.
                    return False
            except KeyError:
                # A KeyError is equivalent to a counter being zero. It
                # indicates that the key has not been inserted into this VICBF.
                return False
        # If we have reached this statement, the query function was unable to
        # rule out the possibility that the key is in the VICBF. Thus, we
        # assume that it is in it. This may be a false positive, but that's to
        # be expected in a bloom filter.
        return True

    def size(self):
        """Return the number of entries in the bloom filter.

        Note: This count is not always reliable, and may even get negative in
        very rare cases: If certain counters encounter an overflow and are
        fixed to their maximum value, keys mapping to these values can be
        removed an arbitrary number of times, each time reducing the internal
        entry count of the bloom filter. This means that the count can
        conceivably fall below zero in very rare cases. If you have an external
        way to verify that you will only remove keys that are in the bloom
        filter, this should not be a problem. Otherwise, keep this in mind.
        This also has implications for the FPR calculation.
        """
        return self.entries

    def FPR(self):
        """Return the current estimated FPR of the bloom filter.

        Please read the comments on the size() function for an important
        limitation of this function.
        """
        return self._calculate_FPR(self.slots, self.size(),
                                   self.hash_functions, self.L)

    def serialize(self):
        """Serialize the VICBF into a binary data structure and return it."""
        serialized = self._build_header()
        # Determine the format it will be serialized in
        if self.bpc == 8:
            # We are using 8-bit counters. This means that we can serialize
            # the counters as 8-bit unsigned integers, which is much more
            # efficient than the alternative below.
            def BFGenerator():
                for i in range(self.slots):
                    try:
                        yield self.BF[i]
                    except KeyError:
                        yield 0
            generator = BFGenerator()
            serialized.append(bytearray(generator))
            # Return the serialized data
            return serialized
        else:
            raise AssertionError("Bad BPC")

    def _build_header(self):
        # Prepare header. Format:
        # - 8 bit hash function count indicator
        # - 32 bit slot count indicator
        # - 4 bit vibase indicator
        # - 4 bit counter size indicator
        header = pack('uint:8, uint:32, uint:32, uint:4, uint:4',
                      self.hash_functions,
                      self.slots,
                      self.entries,
                      self.L,
                      self.bpc)
        return header

    def _calculate_slot_and_increment(self, key, i):
        """Helper function to calculate the slot and increment value"""
        if isinstance(key, (int, long)):
            key = "".join([chr(int(x)) for x in str(key)])
        elif not isinstance(key, str):
            print type(key)
        # Get a sha1 hash of the key, combined with a running integer to
        # arrive at hash_functions different hash functions
        h = hashlib.sha1(key + chr(int(str(i).encode('hex'), 16))).hexdigest()
        # Convert the hash into an index on the bloom filter
        # Yes, it's not efficient or nice, but it does the job.
        slot_index = int(h, 16) % self.slots
        # Get the sha1 hash of the key, combined with the negative running
        # integer to arrive at another different hash function
        h = hashlib.sha1("".join(chr(int(x.encode('hex'), 16)) for x in "-" +
                         str(i)) + key).hexdigest()
        # Again, convert hash into index, this time on the D_L table
        dl_index = int(h, 16) % self.L
        # Compute the increment value
        increment = self.L + dl_index
        # Return the values
        return (slot_index, increment)

    def _calculate_FPR(self, slots, entries, hash_functions, vibase):
        """Helper function to calculate the false positive rate"""
        # Calculate the False Positive Rate of the bloom filter with given
        # parameters
        # Rename parameters to match variables used in the paper
        m = float(slots)
        n = float(max(entries, 0))
        # Set the entry count to at least zero due to the problems described
        # in the documentation of the size() function.
        k = float(hash_functions)
        L = float(vibase)
        # Implement FPR formula from the paper
        fpr = pow(1.0 - pow(1.0 - 1.0 / m, n * k) - ((L - 1.0) / L) *
                  n * k * (1.0 / m) * pow(1.0 - (1.0 / m), n * k - 1.0) -
                  (((L - 1.0) * (L + 1)) / (6.0 * pow(L, 2.0))) *
                  self._binomial(n * k, 2.0) * pow(1.0 / m, 2.0) *
                  pow(1.0 - (1.0 / m), n * k - 2.0),
                  k)
        return fpr

    def _binomial(self, x, y):
        """Helper function to calculate the binomial coefficient"""
        # Source: http://stackoverflow.com/a/26561091/1232833
        try:
            binom = factorial(x) // factorial(y) // factorial(x - y)
        except ValueError:
            binom = 0
        return binom

    def __contains__(self, key):
        """Equivalent to query function, allows "x in y" syntax"""
        return self.query(key)

    def __iadd__(self, key):
        """Shorthand for insert function. Allows "cbf += key" syntax"""
        self.insert(key)
        return self

    def __isub__(self, key):
        """Shorthand for remove function. Allows "cbf -= key" syntax"""
        self.remove(key)
        return self

    def __len__(self):
        """Shorthand for size function. Allows len(x) syntax"""
        return self.size()


def deserialize(serialized):
    hash_functions, slots, size, vibase, bpc = _parse_header(serialized)
    assert bpc == 8
    deser = VICBF(slots, hash_functions, vibase=vibase)
    deser.entries = size

    # The rest of the serialized data contains counter values of bpc bits,
    # in order from slot 0 to slot slots-1
    fmt = 'uint:' + str(bpc)
    # Read in the values and write them into the bloom filter
    for i in range(slots):
        deser.BF[i] = serialized.read(fmt)
    return deser


def _parse_header(serialized):
    """Parse the header and return the contained values.

    Returns the header as (hash_functions, slots, size, vibase, bpc)
    """
    return serialized.readlist('uint:8, uint:32, uint:32, uint:4, uint:4')
