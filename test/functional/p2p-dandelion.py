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

# TODO: Test cases to add:
"""
1. Robustness
   A --[stem]--> TestNode
   TestNode ignores for a minute

 Expect:
   A --[fluff]-> TestNode

2. Resistant to active probing
   A --[stem]--> B
   A <--getdata--- TestNode
 Expect:
     No inv to A
     A --notfound--> TestNode

3. Simulated orphan handling
   A --[stem]{tx1,tx2}--> B --[stem]{tx1,tx2}--> TestNode
   A <--{tx2}-- TestNode

 Expect:
   A --getdata{tx1}--> TestNode

4. A limitation that allows a spy to distinguish the sender

   A --[stem]{tx1}--> B --[stem]{tx1}--> TestNode
  TestNode creates an invalid transaction tx2* that spends tx1
   A <--getdata{00000}-- TestNode
   A <--{tx2*}-- TestNode

 Expect:
   A disconnects TestNode2 immediately
 If A did not actually have tx1, then instead we'd expect:
   A --notfound--> TestNode
   then later disconnect
"""


class DandelionTest(BitcoinTestFramework):

    def __init__(self):
        super().__init__()
        self.num_nodes = 5
        self.setup_clean_chain = False

    def setup_network(self):
        self.extra_args = [[]]*4 + [["-dandelion=0"]]
        #self.extra_args = [["-dandelion=1"]] +[["-dandelion=0"]]*4
        self.setup_nodes()
        connect_nodes(self.nodes[0], 1)
        connect_nodes(self.nodes[1], 2)
        connect_nodes(self.nodes[2], 3)
        connect_nodes(self.nodes[1], 4)

        # Intended communication pattern!
        # 0 --[stem]--> 1 --[stem] --> 2 --[stem]--> 3
        #                              2 <-[fluff]-- 3
        #               1 <-[fluff]--  2
        #               1 --[fluff]---------------------> 4

    def run_test(self):
        node0 = self.nodes[0]
        node1 = self.nodes[1]
        node2 = self.nodes[2]
        node3 = self.nodes[3]
        node4 = self.nodes[4]

        # Get out of IBD
        [ n.generate(1) for n in self.nodes ]

        # Setup the p2p connections and start up the network thread.
        test_node = TestNode()
        connections = []
        connections.append(NodeConn('127.0.0.1', p2p_port(0), self.nodes[0], test_node))

        NetworkThread().start()
        test_node.wait_for_verack()

        self.log.info('Node1.balance %d' % (node1.getbalance(),))
        txids = [node0.sendtoaddress(node0.getnewaddress(), 1) for x in range(30)]

        time.sleep(40)

        [ c.disconnect_node() for c in connections ]

        self.log.info('tmpdir: %s' % (self.options.tmpdir,))

if __name__ == '__main__':
    DandelionTest().main()
