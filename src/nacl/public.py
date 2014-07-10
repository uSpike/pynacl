# Copyright 2013 Donald Stufft and individual contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import, division, print_function

import nacl.c
import nacl.c.crypto_box

from nacl import encoding
from nacl.utils import EncryptedMessage, StringFixer, random


class PublicKey(encoding.Encodable, StringFixer, object):
    """
    The public key counterpart to an Curve25519 :class:`nacl.public.PrivateKey`
    for encrypting messages.

    :param public_key: [:class:`bytes`] Encoded Curve25519 public key
    :param encoder: A class that is able to decode the `public_key`

    :cvar SIZE: The size that the public key is required to be
    """

    SIZE = nacl.c.crypto_box_PUBLICKEYBYTES

    def __init__(self, public_key, encoder=encoding.RawEncoder):
        self._public_key = encoder.decode(public_key)

        if len(self._public_key) != self.SIZE:
            raise ValueError("The public key must be exactly %s bytes long" %
                             self.SIZE)

    def __bytes__(self):
        return self._public_key


class PrivateKey(encoding.Encodable, StringFixer, object):
    """
    Private key for decrypting messages using the Curve25519 algorithm.

    .. warning:: This **must** be protected and remain secret. Anyone who
        knows the value of your :class:`~nacl.public.PrivateKey` can decrypt
        any message encrypted by the corresponding
        :class:`~nacl.public.PublicKey`

    :param private_key: The private key used to decrypt messages
    :param encoder: The encoder class used to decode the given keys

    :cvar SIZE: The size that the private key is required to be
    """

    SIZE = nacl.c.crypto_box_SECRETKEYBYTES

    def __init__(self, private_key, encoder=encoding.RawEncoder):
        # Decode the secret_key
        private_key = encoder.decode(private_key)

        # Verify that our seed is the proper size
        if len(private_key) != self.SIZE:
            raise ValueError(
                "The secret key must be exactly %d bytes long" % self.SIZE)

        raw_public_key = nacl.c.crypto_scalarmult_base(private_key)

        self._private_key = private_key
        self.public_key = PublicKey(raw_public_key)

    def __bytes__(self):
        return self._private_key

    @classmethod
    def generate(cls):
        """
        Generates a random :class:`~nacl.public.PrivateKey` object

        :rtype: :class:`~nacl.public.PrivateKey`
        """
        return cls(random(PrivateKey.SIZE), encoder=encoding.RawEncoder)


class Box(encoding.Encodable, StringFixer, object):
    """
    The Box class boxes and unboxes messages between a pair of keys

    The ciphertexts generated by :class:`~nacl.public.Box` include a 16
    byte authenticator which is checked as part of the decryption. An invalid
    authenticator will cause the decrypt function to raise an exception. The
    authenticator is not a signature. Once you've decrypted the message you've
    demonstrated the ability to create arbitrary valid message, so messages you
    send are repudiable. For non-repudiable messages, sign them after
    encryption.

    :param private_key: :class:`~nacl.public.PrivateKey` used to encrypt and
        decrypt messages
    :param public_key: :class:`~nacl.public.PublicKey` used to encrypt and
        decrypt messages

    :cvar NONCE_SIZE: The size that the nonce is required to be.
    """

    NONCE_SIZE = nacl.c.crypto_box_NONCEBYTES

    def __init__(self, private_key, public_key):
        if private_key and public_key:
            self._shared_key = nacl.c.crypto_box_beforenm(
                public_key.encode(encoder=encoding.RawEncoder),
                private_key.encode(encoder=encoding.RawEncoder),
            )
        else:
            self._shared_key = None

    def __bytes__(self):
        return self._shared_key

    @classmethod
    def decode(cls, encoded, encoder=encoding.RawEncoder):
        # Create an empty box
        box = cls(None, None)

        # Assign our decoded value to the shared key of the box
        box._shared_key = encoder.decode(encoded)

        return box

    def encrypt(self, plaintext, nonce, encoder=encoding.RawEncoder):
        """
        Encrypts the plaintext message using the given `nonce` and returns
        the ciphertext encoded with the encoder.

        .. warning:: It is **VITALLY** important that the nonce is a nonce,
            i.e. it is a number used only once for any given key. If you fail
            to do this, you compromise the privacy of the messages encrypted.

        :param plaintext: [:class:`bytes`] The plaintext message to encrypt
        :param nonce: [:class:`bytes`] The nonce to use in the encryption
        :param encoder: The encoder to use to encode the ciphertext
        :rtype: [:class:`nacl.utils.EncryptedMessage`]
        """
        if len(nonce) != self.NONCE_SIZE:
            raise ValueError("The nonce must be exactly %s bytes long" %
                             self.NONCE_SIZE)

        ciphertext = nacl.c.crypto_box_afternm(
            plaintext,
            nonce,
            self._shared_key,
        )

        encoded_nonce = encoder.encode(nonce)
        encoded_ciphertext = encoder.encode(ciphertext)

        return EncryptedMessage._from_parts(
            encoded_nonce,
            encoded_ciphertext,
            encoder.encode(nonce + ciphertext),
        )

    def decrypt(self, ciphertext, nonce=None, encoder=encoding.RawEncoder):
        """
        Decrypts the ciphertext using the given nonce and returns the
        plaintext message.

        :param ciphertext: [:class:`bytes`] The encrypted message to decrypt
        :param nonce: [:class:`bytes`] The nonce used when encrypting the
            ciphertext
        :param encoder: The encoder used to decode the ciphertext.
        :rtype: [:class:`bytes`]
        """
        # Decode our ciphertext
        ciphertext = encoder.decode(ciphertext)

        if nonce is None:
            # If we were given the nonce and ciphertext combined, split them.
            nonce = ciphertext[:self.NONCE_SIZE]
            ciphertext = ciphertext[self.NONCE_SIZE:]

        if len(nonce) != self.NONCE_SIZE:
            raise ValueError("The nonce must be exactly %s bytes long" %
                             self.NONCE_SIZE)

        plaintext = nacl.c.crypto_box_open_afternm(
            ciphertext,
            nonce,
            self._shared_key,
        )

        return plaintext
