#!/usr/bin/env python3
"""Test processing of dandelion transactions

Setup: two nodes, node0 and node1, not connected to each other.  Node0 does not
whitelist localhost, but node1 does. They will each be on their own chain for
this test.

We have one NodeConn connection to each, test_node and white_node respectively.

The test:
1. Generate one block on each node, to leave IBD.

"""

from test_framework.mininode import *
from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import *
import time

# TestNode: bare-bones "peer".  Used mostly as a conduit for a test to sending
# p2p messages to a node, generating the messages in the main testing logic.
class TestNode(NodeConnCB):
    def __init__(self):
        super().__init__()

class DandelionTest(BitcoinTestFramework):

    def __init__(self):
        super().__init__()
        self.num_nodes = 4
        self.setup_clean_chain = False

    def setup_network(self):
        # Node0 --> 
        self.nodes = []
        self.nodes.append(start_node(0, self.options.tmpdir))
        self.nodes.append(start_node(1, self.options.tmpdir))
        self.nodes.append(start_node(2, self.options.tmpdir))
        self.nodes.append(start_node(3, self.options.tmpdir))
        connect_nodes(self.nodes[0], 1)
        connect_nodes(self.nodes[1], 2)
        connect_nodes(self.nodes[1], 3)

    def run_test(self):
        node0 = self.nodes[0]
        node1 = self.nodes[1]
        node2 = self.nodes[2]
        node3 = self.nodes[3]

        # Get out of IBD
        node1.generate(1)
        sync_blocks(self.nodes)
        
        # Setup the p2p connections and start up the network thread.
        test_node = TestNode()
        connections = []
        connections.append(NodeConn('127.0.0.1', p2p_port(0), self.nodes[0], test_node))
        
        NetworkThread().start()
        test_node.wait_for_verack()

        self.log.info('Node1.balance %d' % (node1.getbalance(),))

        txids = [node0.sendtoaddress(node0.getnewaddress(), 1) for x in range(30)]

        time.sleep(10)

        [ c.disconnect_node() for c in connections ]

        self.log.info('tmpdir: %s' % (self.options.tmpdir,))

if __name__ == '__main__':
    DandelionTest().main()
