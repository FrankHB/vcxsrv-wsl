#!/usr/bin/env python

import unittest
import struct
import itertools
import contextlib
import hashlib
from binascii import unhexlify as unhex
try:
    from math import gcd
except ImportError:
    from fractions import gcd

from eccref import *
from testcrypt import *

def ssh_string(s):
    return struct.pack(">L", len(s)) + s

def find_non_square_mod(p):
    # Find a non-square mod p, using the Jacobi symbol
    # calculation function from eccref.py.
    return next(z for z in itertools.count(2) if jacobi(z, p) == -1)

def fibonacci_scattered(n=10):
    # Generate a list of Fibonacci numbers with power-of-2 indices
    # (F_1, F_2, F_4, ...), to be used as test inputs of varying
    # sizes. Also put F_0 = 0 into the list as a bonus.
    yield 0
    a, b, c = 0, 1, 1
    while True:
        yield b
        n -= 1
        if n <= 0:
            break
        a, b, c = (a**2+b**2, b*(a+c), b**2+c**2)

def fibonacci(n=10):
    # Generate the full Fibonacci sequence starting from F_0 = 0.
    a, b = 0, 1
    while True:
        yield a
        n -= 1
        if n <= 0:
            break
        a, b = b, a+b

def mp_mask(mp):
    # Return the value that mp would represent if all its bits
    # were set. Useful for masking a true mathematical output
    # value (e.g. from an operation that can over/underflow, like
    # mp_sub or mp_anything_into) to check it's right within the
    # ability of that particular mp_int to represent.
    return ((1 << mp_max_bits(mp))-1)

def adjtuples(iterable, n):
    # Return all the contiguous n-tuples of an iterable, including
    # overlapping ones. E.g. if called on [0,1,2,3,4] with n=3 it
    # would return (0,1,2), (1,2,3), (2,3,4) and then stop.
    it = iter(iterable)
    toret = [next(it) for _ in range(n-1)]
    for element in it:
        toret.append(element)
        yield tuple(toret)
        toret[:1] = []

@contextlib.contextmanager
def queued_random_data(nbytes, seed):
    hashsize = 512 // 8
    data = b''.join(
        hashlib.sha512(unicode_to_bytes("preimage:{:d}:{}".format(i, seed)))
        .digest() for i in range((nbytes + hashsize - 1) // hashsize))
    data = data[:nbytes]
    random_queue(data)
    yield None
    random_clear()

def hash_str(alg, message):
    h = ssh_hash_new(alg)
    ssh_hash_update(h, message)
    return ssh_hash_final(h)

def mac_str(alg, key, message, cipher=None):
    m = ssh2_mac_new(alg, cipher)
    ssh2_mac_setkey(m, key)
    ssh2_mac_start(m)
    ssh2_mac_update(m, "dummy")
    # Make sure ssh_mac_start erases previous state
    ssh2_mac_start(m)
    ssh2_mac_update(m, message)
    return ssh2_mac_genresult(m)

class mpint(unittest.TestCase):
    def testCreation(self):
        self.assertEqual(int(mp_new(128)), 0)
        self.assertEqual(int(mp_from_bytes_be(b'ABCDEFGHIJKLMNOP')),
                         0x4142434445464748494a4b4c4d4e4f50)
        self.assertEqual(int(mp_from_bytes_le(b'ABCDEFGHIJKLMNOP')),
                         0x504f4e4d4c4b4a494847464544434241)
        self.assertEqual(int(mp_from_integer(12345)), 12345)
        decstr = '91596559417721901505460351493238411077414937428167'
        self.assertEqual(int(mp_from_decimal_pl(decstr)), int(decstr, 10))
        self.assertEqual(int(mp_from_decimal(decstr)), int(decstr, 10))
        # For hex, test both upper and lower case digits
        hexstr = 'ea7cb89f409ae845215822e37D32D0C63EC43E1381C2FF8094'
        self.assertEqual(int(mp_from_hex_pl(hexstr)), int(hexstr, 16))
        self.assertEqual(int(mp_from_hex(hexstr)), int(hexstr, 16))
        p2 = mp_power_2(123)
        self.assertEqual(int(p2), 1 << 123)
        p2c = mp_copy(p2)
        self.assertEqual(int(p2c), 1 << 123)
        # Check mp_copy really makes a copy, not an alias (ok, that's
        # testing the testcrypt system more than it's testing the
        # underlying C functions)
        mp_set_bit(p2c, 120, 1)
        self.assertEqual(int(p2c), (1 << 123) + (1 << 120))
        self.assertEqual(int(p2), 1 << 123)

    def testBytesAndBits(self):
        x = mp_new(128)
        self.assertEqual(mp_get_byte(x, 2), 0)
        mp_set_bit(x, 2*8+3, 1)
        self.assertEqual(mp_get_byte(x, 2), 1<<3)
        self.assertEqual(mp_get_bit(x, 2*8+3), 1)
        mp_set_bit(x, 2*8+3, 0)
        self.assertEqual(mp_get_byte(x, 2), 0)
        self.assertEqual(mp_get_bit(x, 2*8+3), 0)
        # Currently I expect 128 to be a multiple of any
        # BIGNUM_INT_BITS value we might be running with, so these
        # should be exact equality
        self.assertEqual(mp_max_bytes(x), 128/8)
        self.assertEqual(mp_max_bits(x), 128)

        nb = lambda hexstr: mp_get_nbits(mp_from_hex(hexstr))
        self.assertEqual(nb('00000000000000000000000000000000'), 0)
        self.assertEqual(nb('00000000000000000000000000000001'), 1)
        self.assertEqual(nb('00000000000000000000000000000002'), 2)
        self.assertEqual(nb('00000000000000000000000000000003'), 2)
        self.assertEqual(nb('00000000000000000000000000000004'), 3)
        self.assertEqual(nb('000003ffffffffffffffffffffffffff'), 106)
        self.assertEqual(nb('000003ffffffffff0000000000000000'), 106)
        self.assertEqual(nb('80000000000000000000000000000000'), 128)
        self.assertEqual(nb('ffffffffffffffffffffffffffffffff'), 128)

    def testDecAndHex(self):
        def checkHex(hexstr):
            n = mp_from_hex(hexstr)
            i = int(hexstr, 16)
            self.assertEqual(mp_get_hex(n),
                             unicode_to_bytes("{:x}".format(i)))
            self.assertEqual(mp_get_hex_uppercase(n),
                             unicode_to_bytes("{:X}".format(i)))
        checkHex("0")
        checkHex("f")
        checkHex("00000000000000000000000000000000000000000000000000")
        checkHex("d5aa1acd5a9a1f6b126ed416015390b8dc5fceee4c86afc8c2")
        checkHex("ffffffffffffffffffffffffffffffffffffffffffffffffff")

        def checkDec(hexstr):
            n = mp_from_hex(hexstr)
            i = int(hexstr, 16)
            self.assertEqual(mp_get_decimal(n),
                             unicode_to_bytes("{:d}".format(i)))
        checkDec("0")
        checkDec("f")
        checkDec("00000000000000000000000000000000000000000000000000")
        checkDec("d5aa1acd5a9a1f6b126ed416015390b8dc5fceee4c86afc8c2")
        checkDec("ffffffffffffffffffffffffffffffffffffffffffffffffff")
        checkDec("f" * 512)

    def testComparison(self):
        inputs = [
            "0", "1", "2", "10", "314159265358979", "FFFFFFFFFFFFFFFF",

            # Test over-long versions of some of the same numbers we
            # had short forms of above
            "0000000000000000000000000000000000000000000000000000000000000000"
            "0000000000000000000000000000000000000000000000000000000000000000",

            "0000000000000000000000000000000000000000000000000000000000000000"
            "0000000000000000000000000000000000000000000000000000000000000001",

            "0000000000000000000000000000000000000000000000000000000000000000"
            "0000000000000000000000000000000000000000000000000000000000000002",

            "0000000000000000000000000000000000000000000000000000000000000000"
            "000000000000000000000000000000000000000000000000FFFFFFFFFFFFFFFF",

            "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"
            "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF",
        ]
        values = [(mp_from_hex(s), int(s, 16)) for s in inputs]
        for am, ai in values:
            for bm, bi in values:
                self.assertEqual(mp_cmp_eq(am, bm) == 1, ai == bi)
                self.assertEqual(mp_cmp_hs(am, bm) == 1, ai >= bi)
                if (bi >> 64) == 0:
                    self.assertEqual(mp_eq_integer(am, bi) == 1, ai == bi)
                    self.assertEqual(mp_hs_integer(am, bi) == 1, ai >= bi)

                # mp_min{,_into} is a reasonable thing to test here as well
                self.assertEqual(int(mp_min(am, bm)), min(ai, bi))
                am2 = mp_copy(am)
                mp_min_into(am2, am, bm)
                self.assertEqual(int(am2), min(ai, bi))

    def testConditionals(self):
        testnumbers = [(mp_copy(n),n) for n in fibonacci_scattered()]
        for am, ai in testnumbers:
            for bm, bi in testnumbers:
                cm = mp_copy(am)
                mp_select_into(cm, am, bm, 0)
                self.assertEqual(int(cm), ai & mp_mask(am))
                mp_select_into(cm, am, bm, 1)
                self.assertEqual(int(cm), bi & mp_mask(am))

                mp_cond_add_into(cm, am, bm, 0)
                self.assertEqual(int(cm), ai & mp_mask(am))
                mp_cond_add_into(cm, am, bm, 1)
                self.assertEqual(int(cm), (ai+bi) & mp_mask(am))

                mp_cond_sub_into(cm, am, bm, 0)
                self.assertEqual(int(cm), ai & mp_mask(am))
                mp_cond_sub_into(cm, am, bm, 1)
                self.assertEqual(int(cm), (ai-bi) & mp_mask(am))

                maxbits = max(mp_max_bits(am), mp_max_bits(bm))
                cm = mp_new(maxbits)
                dm = mp_new(maxbits)
                mp_copy_into(cm, am)
                mp_copy_into(dm, bm)

                self.assertEqual(int(cm), ai)
                self.assertEqual(int(dm), bi)
                mp_cond_swap(cm, dm, 0)
                self.assertEqual(int(cm), ai)
                self.assertEqual(int(dm), bi)
                mp_cond_swap(cm, dm, 1)
                self.assertEqual(int(cm), bi)
                self.assertEqual(int(dm), ai)

                if bi != 0:
                    mp_cond_clear(cm, 0)
                    self.assertEqual(int(cm), bi)
                    mp_cond_clear(cm, 1)
                    self.assertEqual(int(cm), 0)

    def testBasicArithmetic(self):
        testnumbers = list(fibonacci_scattered(5))
        testnumbers.extend([1 << (1 << i) for i in range(3,10)])
        testnumbers.extend([(1 << (1 << i)) - 1 for i in range(3,10)])

        testnumbers = [(mp_copy(n),n) for n in testnumbers]

        for am, ai in testnumbers:
            for bm, bi in testnumbers:
                self.assertEqual(int(mp_add(am, bm)), ai + bi)
                self.assertEqual(int(mp_mul(am, bm)), ai * bi)
                # Cope with underflow in subtraction
                diff = mp_sub(am, bm)
                self.assertEqual(int(diff), (ai - bi) & mp_mask(diff))

                for bits in range(0, 512, 64):
                    cm = mp_new(bits)
                    mp_add_into(cm, am, bm)
                    self.assertEqual(int(cm), (ai + bi) & mp_mask(cm))
                    mp_mul_into(cm, am, bm)
                    self.assertEqual(int(cm), (ai * bi) & mp_mask(cm))
                    mp_sub_into(cm, am, bm)
                    self.assertEqual(int(cm), (ai - bi) & mp_mask(cm))

        # A test cherry-picked from the old bignum test script,
        # involving two numbers whose product has a single 1 bit miles
        # in the air and then all 0s until a bunch of cruft at the
        # bottom, the aim being to test that carry propagation works
        # all the way up.
        ai, bi = 0xb4ff6ed2c633847562087ed9354c5c17be212ac83b59c10c316250f50b7889e5b058bf6bfafd12825225ba225ede0cba583ffbd0882de88c9e62677385a6dbdedaf81959a273eb7909ebde21ae5d12e2a584501a6756fe50ccb93b93f0d6ee721b6052a0d88431e62f410d608532868cdf3a6de26886559e94cc2677eea9bd797918b70e2717e95b45918bd1f86530cb9989e68b632c496becff848aa1956cd57ed46676a65ce6dd9783f230c8796909eef5583fcfe4acbf9c8b4ea33a08ec3fd417cf7175f434025d032567a00fc329aee154ca20f799b961fbab8f841cb7351f561a44aea45746ceaf56874dad99b63a7d7af2769d2f185e2d1c656cc6630b5aba98399fa57, 0xb50a77c03ac195225021dc18d930a352f27c0404742f961ca828c972737bad3ada74b1144657ab1d15fe1b8aefde8784ad61783f3c8d4584aa5f22a4eeca619f90563ae351b5da46770df182cf348d8e23b25fda07670c6609118e916a57ce4043608752c91515708327e36f5bb5ebd92cd4cfb39424167a679870202b23593aa524bac541a3ad322c38102a01e9659b06a4335c78d50739a51027954ac2bf03e500f975c2fa4d0ab5dd84cc9334f219d2ae933946583e384ed5dbf6498f214480ca66987b867df0f69d92e4e14071e4b8545212dd5e29ff0248ed751e168d78934da7930bcbe10e9a212128a68de5d749c61f5e424cf8cf6aa329674de0cf49c6f9b4c8b8cc3
        am = mp_copy(ai)
        bm = mp_copy(bi)
        self.assertEqual(int(mp_mul(am, bm)), ai * bi)

        # A regression test for a bug that came up during development
        # of mpint.c, relating to an intermediate value overflowing
        # its container.
        ai, bi = (2**8512 * 2 // 3), (2**4224 * 11 // 15)
        am = mp_copy(ai)
        bm = mp_copy(bi)
        self.assertEqual(int(mp_mul(am, bm)), ai * bi)

    @staticmethod
    def nbits(n):
        # Mimic mp_get_nbits for ordinary Python integers.
        assert 0 <= n
        smax = next(s for s in itertools.count() if (n >> (1 << s)) == 0)
        toret = 0
        for shift in reversed([1 << s for s in range(smax)]):
            if n >> shift != 0:
                n >>= shift
                toret += shift
        assert n <= 1
        if n == 1:
            toret += 1
        return toret

    def testDivision(self):
        divisors = [1, 2, 3, 2**16+1, 2**32-1, 2**32+1, 2**128-159,
                    141421356237309504880168872420969807856967187537694807]
        quotients = [0, 1, 2, 2**64-1, 2**64, 2**64+1, 17320508075688772935]
        for d in divisors:
            for q in quotients:
                remainders = {0, 1, d-1, 2*d//3}
                for r in sorted(remainders):
                    if r >= d:
                        continue # silly cases with tiny divisors
                    n = q*d + r
                    mq = mp_new(self.nbits(q))
                    mr = mp_new(self.nbits(r))
                    mp_divmod_into(n, d, mq, mr)
                    self.assertEqual(int(mq), q)
                    self.assertEqual(int(mr), r)
                    self.assertEqual(int(mp_div(n, d)), q)
                    self.assertEqual(int(mp_mod(n, d)), r)

    def testInversion(self):
        # Test mp_invert_mod_2to.
        testnumbers = [(mp_copy(n),n) for n in fibonacci_scattered()
                       if n & 1]
        for power2 in [1, 2, 3, 5, 13, 32, 64, 127, 128, 129]:
            for am, ai in testnumbers:
                bm = mp_invert_mod_2to(am, power2)
                bi = int(bm)
                self.assertEqual(((ai * bi) & ((1 << power2) - 1)), 1)

                # mp_reduce_mod_2to is a much simpler function, but
                # this is as good a place as any to test it.
                rm = mp_copy(am)
                mp_reduce_mod_2to(rm, power2)
                self.assertEqual(int(rm), ai & ((1 << power2) - 1))

        # Test mp_invert proper.
        moduli = [2, 3, 2**16+1, 2**32-1, 2**32+1, 2**128-159,
                  141421356237309504880168872420969807856967187537694807]
        for m in moduli:
            # Prepare a MontyContext for the monty_invert test below
            # (unless m is even, in which case we can't)
            mc = monty_new(m) if m & 1 else None

            to_invert = {1, 2, 3, 7, 19, m-1, 5*m//17}
            for x in sorted(to_invert):
                if gcd(x, m) != 1:
                    continue # filter out non-invertible cases
                inv = int(mp_invert(x, m))
                assert x * inv % m == 1

                # Test monty_invert too, while we're here
                if mc is not None:
                    self.assertEqual(
                        int(monty_invert(mc, monty_import(mc, x))),
                        int(monty_import(mc, inv)))

    def testMonty(self):
        moduli = [5, 19, 2**16+1, 2**31-1, 2**128-159, 2**255-19,
                  293828847201107461142630006802421204703,
                  113064788724832491560079164581712332614996441637880086878209969852674997069759]

        for m in moduli:
            mc = monty_new(m)

            # Import some numbers
            inputs = [(monty_import(mc, n), n)
                      for n in sorted({0, 1, 2, 3, 2*m//3, m-1})]

            # Check modulus and identity
            self.assertEqual(int(monty_modulus(mc)), m)
            self.assertEqual(int(monty_identity(mc)), int(inputs[1][0]))

            # Check that all those numbers export OK
            for mn, n in inputs:
                self.assertEqual(int(monty_export(mc, mn)), n)

            for ma, a in inputs:
                for mb, b in inputs:
                    xprod = int(monty_export(mc, monty_mul(mc, ma, mb)))
                    self.assertEqual(xprod, a*b % m)

                    xsum = int(monty_export(mc, monty_add(mc, ma, mb)))
                    self.assertEqual(xsum, (a+b) % m)

                    xdiff = int(monty_export(mc, monty_sub(mc, ma, mb)))
                    self.assertEqual(xdiff, (a-b) % m)

                    # Test the ordinary mp_mod{add,sub,mul} at the
                    # same time, even though those don't do any
                    # montying at all

                    xprod = int(mp_modmul(a, b, m))
                    self.assertEqual(xprod, a*b % m)

                    xsum = int(mp_modadd(a, b, m))
                    self.assertEqual(xsum, (a+b) % m)

                    xdiff = int(mp_modsub(a, b, m))
                    self.assertEqual(xdiff, (a-b) % m)

            for ma, a in inputs:
                # Compute a^0, a^1, a^1, a^2, a^3, a^5, ...
                indices = list(fibonacci())
                powers = [int(monty_export(mc, monty_pow(mc, ma, power)))
                          for power in indices]
                # Check the first two make sense
                self.assertEqual(powers[0], 1)
                self.assertEqual(powers[1], a)
                # Check the others using the Fibonacci identity:
                # F_n + F_{n+1} = F_{n+2}, so a^{F_n} a^{F_{n+1}} = a^{F_{n+2}}
                for p0, p1, p2 in adjtuples(powers, 3):
                    self.assertEqual(p2, p0 * p1 % m)

                # Test the ordinary mp_modpow here as well, while
                # we've got the machinery available
                for index, power in zip(indices, powers):
                    self.assertEqual(int(mp_modpow(a, index, m)), power)

        # A regression test for a bug I encountered during initial
        # development of mpint.c, in which an incomplete reduction
        # happened somewhere in an intermediate value.
        b, e, m = 0x2B5B93812F253FF91F56B3B4DAD01CA2884B6A80719B0DA4E2159A230C6009EDA97C5C8FD4636B324F9594706EE3AD444831571BA5E17B1B2DFA92DEA8B7E, 0x25, 0xC8FCFD0FD7371F4FE8D0150EFC124E220581569587CCD8E50423FA8D41E0B2A0127E100E92501E5EE3228D12EA422A568C17E0AD2E5C5FCC2AE9159D2B7FB8CB
        assert(int(mp_modpow(b, e, m)) == pow(b, e, m))

    def testModsqrt(self):
        moduli = [
            5, 19, 2**16+1, 2**31-1, 2**128-159, 2**255-19,
            293828847201107461142630006802421204703,
            113064788724832491560079164581712332614996441637880086878209969852674997069759,
            0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF6FFFFFFFF00000001]
        for p in moduli:
            # Count the factors of 2 in the group. (That is, we want
            # p-1 to be an odd multiple of 2^{factors_of_2}.)
            factors_of_2 = self.nbits((p-1) & (1-p)) - 1
            assert (p & ((2 << factors_of_2)-1)) == ((1 << factors_of_2)+1)

            z = find_non_square_mod(p)

            sc = modsqrt_new(p, z)

            def ptest(x):
                root, success = mp_modsqrt(sc, x)
                r = int(root)
                self.assertTrue(success)
                self.assertEqual((r * r - x) % p, 0)

            def ntest(x):
                root, success = mp_modsqrt(sc, x)
                self.assertFalse(success)

            # Make up some more or less random values mod p to square
            v1 = pow(3, self.nbits(p), p)
            v2 = pow(5, v1, p)
            test_roots = [0, 1, 2, 3, 4, 3*p//4, v1, v2, v1+1, 12873*v1, v1*v2]
            known_squares = {r*r % p for r in test_roots}
            for s in known_squares:
                ptest(s)
                if s != 0:
                    ntest(z*s % p)

            # Make sure we've tested a value that is in each of the
            # subgroups of order (p-1)/2^k but not in the next one
            # (with the exception of k=0, which just means 'have we
            # tested a non-square?', which we have in the above loop).
            #
            # We do this by starting with a known non-square; then
            # squaring it (factors_of_2) times will return values
            # nested deeper and deeper in those subgroups.
            vbase = z
            for k in range(factors_of_2):
                # Adjust vbase by an arbitrary odd power of
                # z, so that it won't look too much like the previous
                # value.
                vbase = vbase * pow(z, (vbase + v1 + v2) | 1, p) % p

                # Move vbase into the next smaller group by squaring
                # it.
                vbase = pow(vbase, 2, p)

                ptest(vbase)

    def testShifts(self):
        x = ((1<<900) // 9949) | 1
        for i in range(2049):
            mp = mp_copy(x)

            mp_lshift_fixed_into(mp, mp, i)
            self.assertEqual(int(mp), (x << i) & mp_mask(mp))

            mp_copy_into(mp, x)
            mp_rshift_fixed_into(mp, mp, i)
            self.assertEqual(int(mp), x >> i)
            self.assertEqual(int(mp_rshift_fixed(x, i)), x >> i)
            self.assertEqual(int(mp_rshift_safe(x, i)), x >> i)

    def testRandom(self):
        # Test random_bits to ensure it correctly masks the return
        # value, and uses exactly as many random bytes as we expect it
        # to.
        for bits in range(512):
            bytes_needed = (bits + 7) // 8
            with queued_random_data(bytes_needed, "random_bits test"):
                mp = mp_random_bits(bits)
                self.assertTrue(int(mp) < (1 << bits))
                self.assertEqual(random_queue_len(), 0)

        # Test mp_random_in_range to ensure it returns things in the
        # right range.
        for rangesize in [2, 3, 19, 35]:
            for lo in [0, 1, 0x10001, 1<<512]:
                hi = lo + rangesize
                bytes_needed = mp_max_bytes(hi) + 16
                for trial in range(rangesize*3):
                    with queued_random_data(
                            bytes_needed,
                            "random_in_range {:d}".format(trial)):
                        v = int(mp_random_in_range(lo, hi))
                        self.assertTrue(lo <= v < hi)

class ecc(unittest.TestCase):
    def testWeierstrassSimple(self):
        # Simple tests using a Weierstrass curve I made up myself,
        # which (unlike the ones used for serious crypto) is small
        # enough that you can fit all the coordinates for a curve on
        # to your retina in one go.

        p = 3141592661
        a, b = -3 % p, 12345
        rc = WeierstrassCurve(p, a, b)
        wc = ecc_weierstrass_curve(p, a, b, None)

        def check_point(wp, rp):
            self.assertTrue(ecc_weierstrass_point_valid(wp))
            is_id = ecc_weierstrass_is_identity(wp)
            x, y = ecc_weierstrass_get_affine(wp)
            if rp.infinite:
                self.assertEqual(is_id, 1)
            else:
                self.assertEqual(is_id, 0)
                self.assertEqual(int(x), int(rp.x))
                self.assertEqual(int(y), int(rp.y))

        def make_point(x, y):
            wp = ecc_weierstrass_point_new(wc, x, y)
            rp = rc.point(x, y)
            check_point(wp, rp)
            return wp, rp

        # Some sample points, including the identity and also a pair
        # of mutual inverses.
        wI, rI = ecc_weierstrass_point_new_identity(wc), rc.point()
        wP, rP = make_point(102, 387427089)
        wQ, rQ = make_point(1000, 546126574)
        wmP, rmP = make_point(102, p - 387427089)

        # Check the simple arithmetic functions.
        check_point(ecc_weierstrass_add(wP, wQ), rP + rQ)
        check_point(ecc_weierstrass_add(wQ, wP), rP + rQ)
        check_point(ecc_weierstrass_double(wP), rP + rP)
        check_point(ecc_weierstrass_double(wQ), rQ + rQ)

        # Check all the special cases with add_general:
        # Adding two finite unequal non-mutually-inverse points
        check_point(ecc_weierstrass_add_general(wP, wQ), rP + rQ)
        # Doubling a finite point
        check_point(ecc_weierstrass_add_general(wP, wP), rP + rP)
        check_point(ecc_weierstrass_add_general(wQ, wQ), rQ + rQ)
        # Adding the identity to a point (both ways round)
        check_point(ecc_weierstrass_add_general(wI, wP), rP)
        check_point(ecc_weierstrass_add_general(wI, wQ), rQ)
        check_point(ecc_weierstrass_add_general(wP, wI), rP)
        check_point(ecc_weierstrass_add_general(wQ, wI), rQ)
        # Doubling the identity
        check_point(ecc_weierstrass_add_general(wI, wI), rI)
        # Adding a point to its own inverse, giving the identity.
        check_point(ecc_weierstrass_add_general(wmP, wP), rI)
        check_point(ecc_weierstrass_add_general(wP, wmP), rI)

        # Verify that point_valid fails if we pass it nonsense.
        bogus = ecc_weierstrass_point_new(wc, int(rP.x), int(rP.y * 3))
        self.assertFalse(ecc_weierstrass_point_valid(bogus))

        # Re-instantiate the curve with the ability to take square
        # roots, and check that we can reconstruct P and Q from their
        # x coordinate and y parity only.
        wc = ecc_weierstrass_curve(p, a, b, find_non_square_mod(p))

        x, yp = int(rP.x), (int(rP.y) & 1)
        check_point(ecc_weierstrass_point_new_from_x(wc, x, yp), rP)
        check_point(ecc_weierstrass_point_new_from_x(wc, x, yp ^ 1), rmP)
        x, yp = int(rQ.x), (int(rQ.y) & 1)
        check_point(ecc_weierstrass_point_new_from_x(wc, x, yp), rQ)

    def testMontgomerySimple(self):
        p, a, b = 3141592661, 0xabc, 0xde

        rc = MontgomeryCurve(p, a, b)
        mc = ecc_montgomery_curve(p, a, b)

        rP = rc.cpoint(0x1001)
        rQ = rc.cpoint(0x20001)
        rdiff = rP - rQ
        rsum = rP + rQ

        def make_mpoint(rp):
            return ecc_montgomery_point_new(mc, int(rp.x))

        mP = make_mpoint(rP)
        mQ = make_mpoint(rQ)
        mdiff = make_mpoint(rdiff)
        msum = make_mpoint(rsum)

        def check_point(mp, rp):
            x = ecc_montgomery_get_affine(mp)
            self.assertEqual(int(x), int(rp.x))

        check_point(ecc_montgomery_diff_add(mP, mQ, mdiff), rsum)
        check_point(ecc_montgomery_diff_add(mQ, mP, mdiff), rsum)
        check_point(ecc_montgomery_diff_add(mP, mQ, msum), rdiff)
        check_point(ecc_montgomery_diff_add(mQ, mP, msum), rdiff)
        check_point(ecc_montgomery_double(mP), rP + rP)
        check_point(ecc_montgomery_double(mQ), rQ + rQ)

    def testEdwardsSimple(self):
        p, d, a = 3141592661, 2688750488, 367934288

        rc = TwistedEdwardsCurve(p, d, a)
        ec = ecc_edwards_curve(p, d, a, None)

        def check_point(ep, rp):
            x, y = ecc_edwards_get_affine(ep)
            self.assertEqual(int(x), int(rp.x))
            self.assertEqual(int(y), int(rp.y))

        def make_point(x, y):
            ep = ecc_edwards_point_new(ec, x, y)
            rp = rc.point(x, y)
            check_point(ep, rp)
            return ep, rp

        # Some sample points, including the identity and also a pair
        # of mutual inverses.
        eI, rI = make_point(0, 1)
        eP, rP = make_point(196270812, 1576162644)
        eQ, rQ = make_point(1777630975, 2717453445)
        emP, rmP = make_point(p - 196270812, 1576162644)

        # Check that the ordinary add function handles all the special
        # cases.

        # Adding two finite unequal non-mutually-inverse points
        check_point(ecc_edwards_add(eP, eQ), rP + rQ)
        check_point(ecc_edwards_add(eQ, eP), rP + rQ)
        # Doubling a finite point
        check_point(ecc_edwards_add(eP, eP), rP + rP)
        check_point(ecc_edwards_add(eQ, eQ), rQ + rQ)
        # Adding the identity to a point (both ways round)
        check_point(ecc_edwards_add(eI, eP), rP)
        check_point(ecc_edwards_add(eI, eQ), rQ)
        check_point(ecc_edwards_add(eP, eI), rP)
        check_point(ecc_edwards_add(eQ, eI), rQ)
        # Doubling the identity
        check_point(ecc_edwards_add(eI, eI), rI)
        # Adding a point to its own inverse, giving the identity.
        check_point(ecc_edwards_add(emP, eP), rI)
        check_point(ecc_edwards_add(eP, emP), rI)

        # Re-instantiate the curve with the ability to take square
        # roots, and check that we can reconstruct P and Q from their
        # y coordinate and x parity only.
        ec = ecc_edwards_curve(p, d, a, find_non_square_mod(p))

        y, xp = int(rP.y), (int(rP.x) & 1)
        check_point(ecc_edwards_point_new_from_y(ec, y, xp), rP)
        check_point(ecc_edwards_point_new_from_y(ec, y, xp ^ 1), rmP)
        y, xp = int(rQ.y), (int(rQ.x) & 1)
        check_point(ecc_edwards_point_new_from_y(ec, y, xp), rQ)

    # For testing point multiplication, let's switch to the full-sized
    # standard curves, because I want to have tested those a bit too.

    def testWeierstrassMultiply(self):
        wc = ecc_weierstrass_curve(p256.p, int(p256.a), int(p256.b), None)
        wG = ecc_weierstrass_point_new(wc, int(p256.G.x), int(p256.G.y))
        self.assertTrue(ecc_weierstrass_point_valid(wG))

        ints = set(i % p256.p for i in fibonacci_scattered(10))
        ints.remove(0) # the zero multiple isn't expected to work
        for i in sorted(ints):
            wGi = ecc_weierstrass_multiply(wG, i)
            x, y = ecc_weierstrass_get_affine(wGi)
            rGi = p256.G * i
            self.assertEqual(int(x), int(rGi.x))
            self.assertEqual(int(y), int(rGi.y))

    def testMontgomeryMultiply(self):
        mc = ecc_montgomery_curve(
            curve25519.p, int(curve25519.a), int(curve25519.b))
        mG = ecc_montgomery_point_new(mc, int(curve25519.G.x))

        ints = set(i % p256.p for i in fibonacci_scattered(10))
        ints.remove(0) # the zero multiple isn't expected to work
        for i in sorted(ints):
            mGi = ecc_montgomery_multiply(mG, i)
            x = ecc_montgomery_get_affine(mGi)
            rGi = curve25519.G * i
            self.assertEqual(int(x), int(rGi.x))

    def testEdwardsMultiply(self):
        ec = ecc_edwards_curve(ed25519.p, int(ed25519.d), int(ed25519.a), None)
        eG = ecc_edwards_point_new(ec, int(ed25519.G.x), int(ed25519.G.y))

        ints = set(i % ed25519.p for i in fibonacci_scattered(10))
        ints.remove(0) # the zero multiple isn't expected to work
        for i in sorted(ints):
            eGi = ecc_edwards_multiply(eG, i)
            x, y = ecc_edwards_get_affine(eGi)
            rGi = ed25519.G * i
            self.assertEqual(int(x), int(rGi.x))
            self.assertEqual(int(y), int(rGi.y))

class standard_test_vectors(unittest.TestCase):
    def testAES(self):
        def vector(cipher, key, plaintext, ciphertext):
            c = ssh2_cipher_new(cipher)
            ssh2_cipher_setkey(c, key)

            # The AES test vectors are implicitly in ECB mode, because
            # they're testing the cipher primitive rather than any
            # mode layered on top of it. We fake this by using PuTTY's
            # CBC setting, and clearing the IV to all zeroes before
            # each operation.

            ssh2_cipher_setiv(c, b'\x00' * 16)
            self.assertEqual(ssh2_cipher_encrypt(c, plaintext), ciphertext)

            ssh2_cipher_setiv(c, b'\x00' * 16)
            self.assertEqual(ssh2_cipher_decrypt(c, ciphertext), plaintext)

        # The test vectors from FIPS 197 appendix C: the key bytes go
        # 00 01 02 03 ... for as long as needed, and the plaintext
        # bytes go 00 11 22 33 ... FF.
        fullkey = struct.pack("B"*32, *range(32))
        plaintext = struct.pack("B"*16, *[0x11*i for i in range(16)])
        vector('aes128', fullkey[:16], plaintext,
               unhex('69c4e0d86a7b0430d8cdb78070b4c55a'))
        vector('aes192', fullkey[:24], plaintext,
               unhex('dda97ca4864cdfe06eaf70a0ec0d7191'))
        vector('aes256', fullkey[:32], plaintext,
               unhex('8ea2b7ca516745bfeafc49904b496089'))

    def testMD5(self):
        MD5 = lambda s: hash_str('md5', s)

        # The test vectors from RFC 1321 section A.5.
        self.assertEqual(MD5(""), unhex('d41d8cd98f00b204e9800998ecf8427e'))
        self.assertEqual(MD5("a"), unhex('0cc175b9c0f1b6a831c399e269772661'))
        self.assertEqual(MD5("abc"), unhex('900150983cd24fb0d6963f7d28e17f72'))
        self.assertEqual(MD5("message digest"),
                         unhex('f96b697d7cb7938d525a2f31aaf161d0'))
        self.assertEqual(MD5("abcdefghijklmnopqrstuvwxyz"),
                         unhex('c3fcd3d76192e4007dfb496cca67e13b'))
        self.assertEqual(MD5("ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                             "abcdefghijklmnopqrstuvwxyz0123456789"),
                         unhex('d174ab98d277d9f5a5611c2c9f419d9f'))
        self.assertEqual(MD5("1234567890123456789012345678901234567890"
                             "1234567890123456789012345678901234567890"),
                         unhex('57edf4a22be3c955ac49da2e2107b67a'))

    def testHmacMD5(self):
        # The test vectors from the RFC 2104 Appendix.
        self.assertEqual(mac_str('hmac_md5', unhex('0b'*16), "Hi There"),
                         unhex('9294727a3638bb1c13f48ef8158bfc9d'))
        self.assertEqual(mac_str('hmac_md5', "Jefe",
                                 "what do ya want for nothing?"),
                         unhex('750c783e6ab0b503eaa86e310a5db738'))
        self.assertEqual(mac_str('hmac_md5', unhex('aa'*16), unhex('dd'*50)),
                         unhex('56be34521d144c88dbb8c733f0e8b3f6'))

    def testEd25519(self):
        def vector(privkey, pubkey, message, signature):
            x, y = ecc_edwards_get_affine(eddsa_public(
                mp_from_bytes_le(privkey), 'ed25519'))
            self.assertEqual(int(y) | ((int(x) & 1) << 255),
                             int(mp_from_bytes_le(pubkey)))
            pubblob = ssh_string(b"ssh-ed25519") + ssh_string(pubkey)
            privblob = ssh_string(privkey)
            sigblob = ssh_string(b"ssh-ed25519") + ssh_string(signature)
            pubkey = ssh_key_new_pub('ed25519', pubblob)
            self.assertTrue(ssh_key_verify(pubkey, sigblob, message))
            privkey = ssh_key_new_priv('ed25519', pubblob, privblob)
            # By testing that the signature is exactly the one expected in
            # the test vector and not some equivalent one generated with a
            # different nonce, we're verifying in particular that we do
            # our deterministic nonce generation in the manner specified
            # by Ed25519. Getting that wrong would lead to no obvious
            # failure, but would surely turn out to be a bad idea sooner
            # or later...
            self.assertEqual(ssh_key_sign(privkey, message, 0), sigblob)

        # A cherry-picked example from DJB's test vector data at
        # https://ed25519.cr.yp.to/python/sign.input, which is too
        # large to copy into here in full.
        privkey = unhex(
            'c89955e0f7741d905df0730b3dc2b0ce1a13134e44fef3d40d60c020ef19df77')
        pubkey = unhex(
            'fdb30673402faf1c8033714f3517e47cc0f91fe70cf3836d6c23636e3fd2287c')
        message = unhex(
            '507c94c8820d2a5793cbf3442b3d71936f35fe3afef316')
        signature = unhex(
            '7ef66e5e86f2360848e0014e94880ae2920ad8a3185a46b35d1e07dea8fa8ae4'
            'f6b843ba174d99fa7986654a0891c12a794455669375bf92af4cc2770b579e0c')
        vector(privkey, pubkey, message, signature)

        # You can get this test program to run the full version of
        # DJB's test vectors by modifying the source temporarily to
        # set this variable to a pathname where you downloaded the
        # file.
        ed25519_test_vector_path = None
        if ed25519_test_vector_path is not None:
            with open(ed25519_test_vector_path) as f:
                for line in iter(f.readline, ""):
                    words = line.split(":")
                    # DJB's test vector input format concatenates a
                    # spare copy of the public key to the end of the
                    # private key, and a spare copy of the message to
                    # the end of the signature. Strip those off.
                    privkey = unhex(words[0])[:32]
                    pubkey = unhex(words[1])
                    message = unhex(words[2])
                    signature = unhex(words[3])[:64]
                    vector(privkey, pubkey, message, signature)

if __name__ == "__main__":
    try:
        unittest.main()
    finally:
        # On exit, make sure we check the subprocess's return status,
        # so that if Leak Sanitiser detected any memory leaks, the
        # test will turn into a failure at the last minute.
        childprocess.check_return_status()
