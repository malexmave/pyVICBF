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


class VICBFError(Exception):
    def __init__(self, message):
        self.message = message


class VICBF():
    """A basic VICBF implementation"""

    """Counstructor for the VICBF.

    Attributes:
        slots -- The number of slots (counters) the bloom filter should use.
        called "m" in the paper.

        expected_entries -- The expected maximum number of entries the bloom
        filter will contain at any one time. Called |S| = n in the paper.

        hash_functions -- The number of hash functions to use. Called k in the
        paper.

        vibase -- The base for the variable-increment lookup table. Called L
        in the paper. A good value seems to be 4 or 8, according to the paper.
        Must be one of 2, 4, 8, 16.
    """
    def __init__(self, slots, expected_entries, hash_functions, vibase=4):
        # TODO See if I can change the parameter to state a desired FPR
        if hash_functions < 1:
            raise VICBFError("hash_functions must be >=1")
        if expected_entries < 1:
            raise VICBFError("expected_entries must be >=1")
        if hash_functions < 1:
            raise VICBFError("hash_functions must be >=1")
        if vibase not in (2, 4, 8, 16):
            raise VICBFError("vibase must be one of 2, 4, 8, 16")
        self.BF = {}
        self.slots = slots
        self.expected_entries = expected_entries
        self.hash_functions = hash_functions
        self.L = vibase
        self.m = 8  # Number of bits per counter

    """Insert a value into the bloom filter

    Arguments:
        key -- the key to insert."""
    def insert(self, key):
        if key is None:
            raise VICBFError("Key cannot be None")
        for i in range(self.hash_functions):
            # Compute the slot index and increment value
            slot_index, increment = self._get_values(key, i)
            # Perform the increment in the bloom filter
            try:
                if self.BF[slot_index] + increment >= 2 ** self.m - 1:
                    self.BF[slot_index] = 2 ** self.m - 1
                else:
                    self.BF[slot_index] += increment
            except KeyError:
                self.BF[slot_index] = increment

    def remove(self, key):
        if key is None:
            raise VICBFError("Key cannot be None")
        for i in range(self.hash_functions):
            # Compute the slot and increment values
            slot_index, decrement = self._get_values(key, i)
            # Perform the decrement in the bloom filter
            try:
                if self.BF[slot_index] == 2 ** self.m - 1:
                    # If the counter experienced an overflow, we cannot modify
                    # it, as that may lead to false negatives in the long run.
                    # Leave it as it is and continue on
                    continue
                elif self.BF[slot_index] - decrement < 0:
                    # After the decrement, the counter would be negative.
                    # This should be impossible and indicates incorrect usage.
                    raise VICBFError("Trying to remove entry not in VICBF")
                elif self.BF[slot_index] - decrement == 0:
                    # After the decrement, the counter is zero. Remove the
                    # entry from the hashtable to save space
                    del self.BF[slot_index]
                else:
                    # After the decrement, the counter will still be positive.
                    # Perform the decrement
                    self.BF[slot_index] -= decrement
            except KeyError:
                # A KeyError should not occur if the item is in the VICBF, so
                # this indicates incorrect usage. Raise an exception
                raise VICBFError("Trying to remove entry not in VICBF")

    def query(self, key):
        if key is None:
            raise VICBFError("Key cannot be None")
        for i in range(self.hash_functions):
            # Compute the slot and increment values
            slot_index, decrement = self._get_values(key, i)
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

    def serialize(self):
        pass

    def _get_values(self, key, i):
        # Get a sha1 hash of the key, combined with a running integer to
        # arrive at hash_functions different hash functions
        h = hashlib.sha1(str(key) + str(i)).hexdigest()
        # Convert the hash into an index on the bloom filter
        # Yes, it's not efficient or nice, but it does the job.
        slot_index = int(h, 16) % self.slots
        # Get the sha1 hash of the key, combined with the negative running
        # integer to arrive at another different hash function
        h = hashlib.sha1(str(-i) + str(key)).hexdigest()
        # Again, convert hash into index, this time on the D_L table
        dl_index = int(h, 16) % self.L
        # Compute the increment value
        increment = self.L + dl_index
        # Return the values
        return (slot_index, increment)
