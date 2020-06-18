from icmplib import ICMPv4Socket, TimeoutExceeded, ICMPRequest, ICMPSocketError
import socket
from struct import pack, unpack
from time import time

# This class inherits from icmplib.ICMPv4Socket
# It provides an additional method receiveAny() which is capable of sniffing any incoming ICMP messages
# That is, it won't attempt to match up the id and sequence number to a previously sent ICMP ping message

class customICMPv4Socket(ICMPv4Socket):
    #
    def receiveAny(self):
        '''
        Receive a reply from a host.

        This method can be called multiple times if you expect several
        responses (as with a broadcast address).

        :raises TimeoutExceeded: If no response is received before the
            timeout defined in the request.
            This exception is also useful for stopping a possible loop
            in case of multiple responses.
        :raises ICMPSocketError: If another error occurs while
            receiving.

        :rtype: ICMPReply
        :returns: An ICMPReply object containing the reply of the
            desired destination.

        See the ICMPReply class for details.

        '''
        if not self._last_request:
            raise TimeoutExceeded(0)

        request = self._last_request

        current_time = time()
        self._socket.timeout = request.timeout
        timeout = current_time + request.timeout

        try:
            while True:
                packet, address, port = self._socket.receive()
                reply_time = time()

                if reply_time > timeout:
                    raise socket.timeout

                reply = self._read_reply(
                    packet=packet,
                    source=address,
                    reply_time=reply_time)

                ######### JT mods. By commenting out this test, all incoming ICMP messages will be returned
                # if (request.id == reply.id and
                #     request.sequence == reply.sequence):
                return reply

        except socket.timeout:
            raise TimeoutExceeded(request.timeout)

        except OSError as err:
            raise ICMPSocketError(str(err))

