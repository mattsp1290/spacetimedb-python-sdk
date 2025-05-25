"""
BSATN exception classes.

These exceptions mirror the error types used in the Go implementation
for consistency across language bindings.
"""


class BsatnError(Exception):
    """Base exception for all BSATN-related errors."""
    pass


class BsatnInvalidTagError(BsatnError):
    """Raised when an invalid type tag is encountered."""
    pass


class BsatnBufferTooSmallError(BsatnError):
    """Raised when the buffer is too small for the operation."""
    pass


class BsatnInvalidUTF8Error(BsatnError):
    """Raised when invalid UTF-8 data is encountered."""
    pass


class BsatnOverflowError(BsatnError):
    """Raised when an integer overflow occurs."""
    pass


class BsatnInvalidFloatError(BsatnError):
    """Raised when an invalid float value (NaN or Inf) is encountered."""
    pass


class BsatnTooLargeError(BsatnError):
    """Raised when a payload is too large."""
    pass
