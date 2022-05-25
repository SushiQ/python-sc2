from datetime import datetime
from abc import ABC, abstractmethod
from enum import Enum, auto
from time import sleep


global seconds
seconds = 6

class FastBaseBot():
    def __init__(self, clock):
        clock = BTNode()
        self.clock = clock

class State(Enum):
    RUNNING = auto()
    SUCCESS = auto()
    FAILURE = auto()


class BTNode(FastBaseBot):
    def __init__(self):
        self._nodeState = State.FAILURE

    def set_state(self, state):
        self._nodeState = state

    def get_state(self):
        return self._nodeState

    @abstractmethod
    def Evaluate(self):
        pass


class Selector(BTNode):
    print("IN Selector")

    def __init__(self, nodes):
        self.node_list = nodes;

    def Selector(node_list):
        self.node_list = node_list;

    def Evaluate():
        print("IN Selector -> Evaluate")

        print("node_list = ", self.node_list)

        for node in self.node_list:
            if node.Evaluate() == State.RUNNING:
                _nodeState = State.RUNNING
                return _nodeState
            elif node.Evaluate() == State.SUCCESS:
                    _nodeState = State.SUCCESS
                    return _nodeState
            elif node.Evaluate() == State.FAILURE:
                    break
            else:
                break

            _nodeState = State.FAILURE
            return _nodeState


class Sequence(BTNode):
    print("IN Sequence")
    def __init__(self, nodes):
        self.node_list = nodes;

    def Sequence(node_list):
        self.node_list = node_list;

    def Evaluate(self):
        print("IN Sequence -> Evaluate")

        isAnyNodeRunning = False
        print("node_list = ", self.node_list)

        #for node in self.node_list:
        i = 0

        while i < len(self.node_list):
            node = self.node_list[i]
            print("i = ", i, " and node = ", node)
            node._nodeState = node.Evaluate()
            print("node._nodeState = ", node._nodeState)

            if node._nodeState == State.SUCCESS:
                print("!! Evaluate next node")
                self.node_list[i].Evaluate()
                i += 1
                continue

            else:
                print("?? Evaluate this node")

                node._nodeState = node.Evaluate()

            #_nodeState = State.FAILURE
            #return _nodeState

        if isAnyNodeRunning:
            _nodeState = State.RUNNING
        else:
            _nodeState = State.SUCCESS

        return _nodeState


class twoSecond(BTNode):
    print("twoSecond! ")

    def Evaluate(self):
        print("twoSecond -> Evaluate! ")

        if seconds % 2 == 0:
            print("self._nodeState Before: ", self._nodeState)

            print("1. seconds= ", seconds)

            print("1. True!")
            self._nodeState = State.SUCCESS
            print("self._nodeState After: ", self._nodeState)
            return State.SUCCESS

        else:
            print("1. seconds = ", seconds)

            print("1. False!")
            self._nodeState = State.FAILURE
            return State.FAILURE


class threeSecond(BTNode):
    def Evaluate(self):

        if seconds % 3 == 0:
            print("2. Also True!")
            self._nodeState = State.SUCCESS
            return State.SUCCESS
        else:
            print("2. False!")
            self._nodeState = State.FAILURE
            return State.FAILURE


class fourSecond(BTNode):
    def Evaluate(self):

        if seconds % 4 == 0:
            print("3. ALSO ALSO True!")
            self._nodeState = State.SUCCESS
            return State.SUCCESS
        else:
            print("3. False!")
            self._nodeState = State.FAILURE
            return State.FAILURE


class BehaviorTree():
    checkTwoSecond = twoSecond()
    #checkTwoSecond.Evaluate()

    checkThreeSecond = threeSecond()
    #checkThreeSecond.Evaluate()

    checkFourSecond = fourSecond()

    #clockSequence = BTNode()
    clockSequence = Sequence( [checkTwoSecond, checkThreeSecond, checkFourSecond] )
    #print([checkTwoSecond.Evaluate(), checkThreeSecond.Evaluate()])
    clockSequence.Evaluate()
