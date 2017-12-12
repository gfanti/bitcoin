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
2. Test loop behavior
   Stem: 3 ----> 4 ----> 5 ----> 3; each node with "-dandelion=1.0"
   Node 3 generates a transaction: 0.1 BTC from Node 3 to Node 5
   Wait until the loop has almost certainly been traversed by the transaction
   TestNode 2 sends getdata for this txn to Node 3
   Nominal results: Node 3 replies with notfound
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
    self.num_nodes = 6
    self.setup_clean_chain = False # Results in nodes having a balance to spend
    self.nodes = None
    self.extra_args = [["-dandelion=1.0"],["-dandelion=1.0"],["-dandelion=1.0"],
                       ["-dandelion=1.0"],["-dandelion=1.0"],["-dandelion=1.0"]]

  def setup_network(self):
    self.setup_nodes()
    # 0 ----> 1 ----> 2
    connect_nodes(self.nodes[0],1)
    connect_nodes(self.nodes[1],2)
    # 3 ----> 4 ----> 5 ----> 3
    connect_nodes(self.nodes[3],4)
    connect_nodes(self.nodes[4],5)
    connect_nodes(self.nodes[5],3)

  def run_test(self):
    # Convenience variables
    node0 = self.nodes[0]
    node1 = self.nodes[1]
    node2 = self.nodes[2]
    stem1 = [node0, node1, node2]
    node3 = self.nodes[3]
    node4 = self.nodes[4]
    node5 = self.nodes[5]
    stem2 = [node3, node4, node5]
    # Test 1 variables and connections
    t1_test_node = TestNode()
    t1_test_conn = NodeConn('127.0.0.1',p2p_port(1),node0,t1_test_node)
    t1_test_node.add_connection(t1_test_conn)
    # Test 2 variables and connections
    t2_test_node = TestNode()
    t2_test_conn = NodeConn('127.0.0.1',p2p_port(2),node3,t2_test_node)
    t2_test_node.add_connection(t2_test_conn)
    # Get out of Initial Block Download (IBD)
    # Note: Generating a block at each root and using sync_blocks() would fail
    #       for nodes with "-dandelion=1.0"
    for node in self.nodes:
      node.generate(1)
    # Start networking thread
    NetworkThread().start()
    time.sleep(1)
    # Test 1: Resistance to active probing while in stem phase
    t1_txid = node0.sendtoaddress(node2.getnewaddress(),0.1)
    t1_tx = FromHex(CTransaction(),node0.gettransaction(t1_txid)['hex'])
    assert(not 'notfound' in t1_test_node.message_count)
    t1_test_node.getdata(t1_tx.calc_sha256(True))
    time.sleep(1)
    assert('notfound' in t1_test_node.message_count)
    self.log.info('Success: resistance to stem phase active probing')
    # Test 2: Loop behavior
    t2_txid = node3.sendtoaddress(node5.getnewaddress(),0.1)
    t2_tx = FromHex(CTransaction(),node3.gettransaction(t2_txid)['hex'])
    assert(not 'notfound' in t2_test_node.message_count)
    time.sleep(30) # Wait until the loop has almost certainly been traversed
    t2_test_node.getdata(t2_tx.calc_sha256(True))
    time.sleep(1)
    assert('notfound' in t2_test_node.message_count)
    self.log.info('Success: loop behavior')

if __name__ == '__main__':
  DandelionTest().main()
