#!/usr/bin/env python3
# Copyright (c) 2017 Bradley Denby
# Distributed under the MIT software license. See the accompanying file COPYING
# or http://www.opensource.org/licenses/mit-license.php.
"""Test transaction behaviors under the Dandelion spreading policy

There are three nodes on one stem: 0 ----> 1 ----> 2

Tests:
0. Generate a block for each node in order to leave Initial Block Download (IBD)
1. Test for resistance to active probing while in stem phase:
   Stem: 0 ----> 1 ----> 2; each node with "-dandelion=1.0"
   Node 0 generates a transaction: 0.1 BTC from Node 0 to Node 2
   TestNode 1 sends getdata for this txn to Node 0
   Nominal results: Node 0 replies with notfound
"""

from test_framework.mininode import *                          # NodeConnCB
from test_framework.test_framework import BitcoinTestFramework # BitcoinTestFramework
from test_framework.util import *                              # other stuff
import time                                                    # sleep

class TestNode(NodeConnCB):
  def __init__(self):
    super().__init__()

  def getdata(self, tx_hash):
    msg = msg_getdata()
    msg.inv.append(CInv(1,tx_hash))
    self.connection.send_message(msg)

class DandelionTest(BitcoinTestFramework):
  def __init__(self):
    super().__init__()
    self.num_nodes = 3
    self.setup_clean_chain = False # Results in nodes having a balance to spend
    self.nodes = None
    self.extra_args = [["-dandelion=1.0"],["-dandelion=1.0"],["-dandelion=1.0"]]

  def setup_network(self):
    self.setup_nodes()
    # 0 ----> 1 ----> 2
    connect_nodes(self.nodes[0],1)
    connect_nodes(self.nodes[1],2)

  def run_test(self):
    # Convenience variables
    node0 = self.nodes[0]
    node1 = self.nodes[1]
    node2 = self.nodes[2]
    stem = [node0, node1, node2]
    # Get out of Initial Block Download (IBD)
    # Note: Generating a block at each root and using sync_blocks() would fail
    #       for nodes with "-dandelion=1.0"
    for node in self.nodes:
      node.generate(1)
    # Test 1: Resistance to active probing while in stem phase
    t1_test_node = TestNode()
    t1_test_conn = NodeConn('127.0.0.1',p2p_port(0),node0,t1_test_node)
    t1_test_node.add_connection(t1_test_conn)
    NetworkThread().start()
    time.sleep(1)
    t1_txid = node0.sendtoaddress(node2.getnewaddress(),0.1)
    t1_tx = FromHex(CTransaction(),node0.gettransaction(t1_txid)['hex'])
    assert(not 'notfound' in t1_test_node.message_count)
    t1_test_node.getdata(t1_tx.calc_sha256(True))
    time.sleep(1)
    assert('notfound' in t1_test_node.message_count)
    self.log.info('Success: resistance to stem phase active probing')

if __name__ == '__main__':
  DandelionTest().main()
