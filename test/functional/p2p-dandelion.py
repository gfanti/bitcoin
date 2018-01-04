#!/usr/bin/env python3
# Copyright (c) 2017-2018 Bradley Denby
# Distributed under the MIT software license. See the accompanying file COPYING
# or http://www.opensource.org/licenses/mit-license.php.
"""Test transaction behaviors under the Dandelion spreading policy

Tests:
1. Resistance to active probing:
   Stem:  0 --> 1 --> 2 --> 0 where each node has argument "-dandelion=1.0"
   Probe: TestNode --> 0
   Node 0 generates a transaction, "tx": 0.1 BTC from Node 0 to Node 2
   TestNode immediately sends getdata for tx to Node 0
   Assert that Node 0 replies with notfound

2. Loop behavior:
   Stem:  0 --> 1 --> 2 --> 0 where each node has argument "-dandelion=1.0"
   Probe: TestNode --> 0
   Wait 20 seconds after Test 1, then TestNode sends getdata for tx to Node 0
   Assert that Node 0 replies with notfound

3. Resistance to black holes:
   Stem:  0 --> 1 --> 2 --> 0 where each node has argument "-dandelion=1.0"
   Probe: TestNode --> 0
   Wait 40 seconds after Test 2, then TestNode sends getdata for tx to Node 0
   Assert that Node 0 replies with tx

4. Multiple transaction routing (defence against intersection attacks):
   Stem:  3 --> 5 --> 6 where each node has argument "-dandelion=1.0"
               ^ \
              /   v
             4     7
   Probes: TestNode --> 6, TestNode --> 7
   Node 3 generates 3 transactions of 0.1 BTC from Node 3 to Node 5
   Node 4 generates 3 transactions of 0.1 BTC from Node 4 to Node 5
   Wait 20 seconds (allows stem propagation), then disconnect all nodes
   Wait 40 seconds (ensures fluff phase), then TestNode6 sends getdata for
   transactions to Node 6 and TestNode7 sends getdata for transactions to Node 7
   Assert that each transaction has exactly one destination
   Assert that all transactions from the same node have the same destination
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
    self.num_nodes = 8
    self.setup_clean_chain = True
    self.nodes = None
    self.extra_args = [["-dandelion=1.0"],["-dandelion=1.0"],["-dandelion=1.0"],
                       ["-dandelion=1.0"],["-dandelion=1.0"],["-dandelion=1.0"],
                       ["-dandelion=1.0"],["-dandelion=1.0"]]

  def setup_network(self):
    self.setup_nodes()
    # Tests 1,2,3: 0 --> 1 --> 2 --> 0
    connect_nodes(self.nodes[0],1)
    connect_nodes(self.nodes[1],2)
    connect_nodes(self.nodes[2],0)
    # Test 4: 3 --> 5 --> 6
    #              ^ \
    #             /   v
    #            4     7
    connect_nodes(self.nodes[3],5)
    connect_nodes(self.nodes[4],5)
    connect_nodes(self.nodes[5],6)
    connect_nodes(self.nodes[5],7)

  def run_test(self):
    # Convenience variables
    node0 = self.nodes[0]
    node1 = self.nodes[1]
    node2 = self.nodes[2]
    node3 = self.nodes[3]
    node4 = self.nodes[4]
    node5 = self.nodes[5]
    node6 = self.nodes[6]
    node7 = self.nodes[7]

    # Setup TestNodes
    test_node0 = TestNode()
    test_conn0 = NodeConn('127.0.0.1',p2p_port(0),node0,test_node0)
    test_node0.add_connection(test_conn0)
    test_node6 = TestNode()
    test_conn6 = NodeConn('127.0.0.1',p2p_port(6),node6,test_node6)
    test_node6.add_connection(test_conn6)
    test_node7 = TestNode()
    test_conn7 = NodeConn('127.0.0.1',p2p_port(7),node7,test_node7)
    test_node7.add_connection(test_conn7)

    # Get out of Initial Block Download (IBD)
    for node in self.nodes:
      node.generate(1)
    # Generate funds for node0
    node0.generate(101)
    # Generate funds for node3
    node3.generate(101)
    node3.generate(1)
    node3.generate(1)
    # Generate funds for node4
    node4.generate(101)
    node4.generate(1)
    node4.generate(1)

    # Start networking thread
    NetworkThread().start()
    time.sleep(1)

    # Tests 1,2,3
    # There is a low probability that one of these tests will fail even if the
    # implementation is correct. Thus, these tests are repeated upon failure. A
    # true bug will result in repeated failures.
    self.log.info('Starting tests...')
    test_1_passed = False
    test_2_passed = False
    test_3_passed = False
    tries_left = 3
    while(not (test_1_passed and test_2_passed and test_3_passed) and tries_left > 0):
      tries_left -= 1
      # Test 1: Resistance to active probing
      test_node0.message_count['notfound'] = 0
      node0_txid = node0.sendtoaddress(node2.getnewaddress(),0.1)
      node0_tx = FromHex(CTransaction(),node0.gettransaction(node0_txid)['hex'])
      test_node0.getdata(node0_tx.calc_sha256(True))
      time.sleep(1)
      try:
        assert(test_node0.message_count['notfound']==1)
        if not test_1_passed:
          test_1_passed = True
          self.log.info('Success: resistance to active probing')
      except AssertionError:
        if not test_1_passed and tries_left == 0:
          self.log.info('Failed: resistance to active probing')
      # Test 2: Loop behavior
      test_node0.message_count['notfound'] = 0
      time.sleep(20)
      test_node0.getdata(node0_tx.calc_sha256(True))
      time.sleep(1)
      try:
        assert(test_node0.message_count['notfound']==1)
        if not test_2_passed:
          test_2_passed = True
          self.log.info('Success: loop behavior')
      except AssertionError:
        if not test_2_passed and tries_left == 0:
          self.log.info('Failed: loop behavior')
      # Test 3: Resistance to black holes
      test_node0.message_count['tx'] = 0
      time.sleep(40)
      test_node0.getdata(node0_tx.calc_sha256(True))
      time.sleep(1)
      try:
        assert(test_node0.message_count['tx']==1)
        if not test_3_passed:
          test_3_passed = True
          self.log.info('Success: resistance to black holes')
      except AssertionError:
        if not test_3_passed and tries_left == 0:
          self.log.info('Failed: resistance to black holes')

    # Test 4
    ## Node 3 Sent Transactions
    node3_tx_count = 3
    node3_txids = []
    node3_txs = []
    for i in range(node3_tx_count):
      node3_txids.append(node3.sendtoaddress(node5.getnewaddress(),0.1))
      node3_txs.append(FromHex(CTransaction(),node3.gettransaction(node3_txids[i])['hex']))
    ## Node 4 Sent Transactions
    node4_tx_count = 3
    node4_txids = []
    node4_txs = []
    for i in range(node4_tx_count):
      node4_txids.append(node4.sendtoaddress(node5.getnewaddress(),0.1))
      node4_txs.append(FromHex(CTransaction(),node4.gettransaction(node4_txids[i])['hex']))
    ## Node 6 Received Transactions
    tx_received_node6 = {} # Dictionary: tx received at node 6? True/False
    for i in range(node3_tx_count):
      tx_received_node6[node3_txs[i].vin[0].prevout.hash] = False
    for i in range(node4_tx_count):
      tx_received_node6[node4_txs[i].vin[0].prevout.hash] = False
    ## Node 7 Received Transactions
    tx_received_node7 = {} # Dictionary: tx received at node 7? True/False
    for i in range(node3_tx_count):
      tx_received_node7[node3_txs[i].vin[0].prevout.hash] = False
    for i in range(node4_tx_count):
      tx_received_node7[node4_txs[i].vin[0].prevout.hash] = False
    ## Wait for stem phase propagation
    time.sleep(20)
    ## Disconnect nodes
    disconnect_nodes(self.nodes[3],5)
    disconnect_nodes(self.nodes[4],5)
    disconnect_nodes(self.nodes[5],6)
    disconnect_nodes(self.nodes[5],7)
    ## Wait for fluff phase
    time.sleep(40)
    ## Probe Node 6
    node6_node3_tx_count = 0 # Number of txs from node3 received by node6
    node6_node4_tx_count = 0 # Number of txs from node4 received by node6
    node6_notfound_count = 0
    test_node6.message_count['notfound'] = node6_notfound_count
    for i in range(node3_tx_count):
      test_node6.getdata(node3_txs[i].calc_sha256(True))
      time.sleep(1)
      if test_node6.message_count['notfound'] == node6_notfound_count:
        tx_hash = test_node6.last_message['tx'].tx.vin[0].prevout.hash
        if tx_hash in tx_received_node6:
          tx_received_node6[tx_hash] = True
          node6_node3_tx_count += 1
      else:
        node6_notfound_count = test_node6.message_count['notfound']
    for i in range(node4_tx_count):
      test_node6.getdata(node4_txs[i].calc_sha256(True))
      time.sleep(1)
      if test_node6.message_count['notfound'] == node6_notfound_count:
        tx_hash = test_node6.last_message['tx'].tx.vin[0].prevout.hash
        if tx_hash in tx_received_node6:
          tx_received_node6[tx_hash] = True
          node6_node4_tx_count += 1
      else:
        node6_notfound_count = test_node6.message_count['notfound']
    ## Probe Node 7
    node7_node3_tx_count = 0 # Number of txs from node3 received by node7
    node7_node4_tx_count = 0 # Number of txs from node4 received by node7
    node7_notfound_count = 0
    test_node7.message_count['notfound'] = node7_notfound_count
    for i in range(node3_tx_count):
      test_node7.getdata(node3_txs[i].calc_sha256(True))
      time.sleep(1)
      if test_node7.message_count['notfound'] == node7_notfound_count:
        tx_hash = test_node7.last_message['tx'].tx.vin[0].prevout.hash
        if tx_hash in tx_received_node7:
          tx_received_node7[tx_hash] = True
          node7_node3_tx_count += 1
      else:
        node7_notfound_count = test_node7.message_count['notfound']
    for i in range(node4_tx_count):
      test_node7.getdata(node4_txs[i].calc_sha256(True))
      time.sleep(1)
      if test_node7.message_count['notfound'] == node7_notfound_count:
        tx_hash = test_node7.last_message['tx'].tx.vin[0].prevout.hash
        if tx_hash in tx_received_node7:
          tx_received_node7[tx_hash] = True
          node7_node4_tx_count += 1
      else:
        node7_notfound_count = test_node7.message_count['notfound']
    ## Check that the total number of messages is correct
    test_4_passed = (
     (node6_node3_tx_count+node7_node3_tx_count==node3_tx_count) and \
     (node7_node3_tx_count+node7_node4_tx_count==node4_tx_count))
    ## Check that all transactions from the same node have the same destination
    if test_4_passed:
      if node6_node3_tx_count>0:
        test_4_passed = test_4_passed and (node6_node3_tx_count==node3_tx_count)
      if node6_node4_tx_count>0:
        test_4_passed = test_4_passed and (node6_node4_tx_count==node4_tx_count)
      if node7_node3_tx_count>0:
        test_4_passed = test_4_passed and (node7_node3_tx_count==node3_tx_count)
      if node7_node4_tx_count>0:
        test_4_passed = test_4_passed and (node7_node4_tx_count==node4_tx_count)
    ## Log results
    if test_4_passed:
      self.log.info('Success: multiple transaction routing')
    else:
      self.log.info('Failed: multiple transaction routing')

    all_tests_passed = test_1_passed and test_2_passed and test_3_passed and test_4_passed
    assert(all_tests_passed)

if __name__ == '__main__':
  DandelionTest().main()
