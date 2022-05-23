from datetime import datetime
from abc import ABC, abstractmethod

#get current date
dt = datetime.today()
seconds = round(dt.timestamp())
print(seconds)

BT = True


class FastBaseBot():
    clock.self = BTNode()

    while BT:
        clock.Evaluate()


class BehaviorTree():

        clockSequence = [ twoSecond, threeSecond]
        clock = clockSequence


class State(Enum):
    RUNNING = auto()
    SUCCESS = auto()
    FAILURE = auto()


class BTNode(FastBaseBot):
    _nodeState = State("_nodeState")
    def nodeState():
        return _nodeState

    @abstractmethod
    def Evaluate(self):
        pass


class Selector(BTNode):
    nodes = []

    def Selector(node_list):
        self.node_list = node_list;


    def Evaluate():
        for node in nodes:
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
    nodes = []

    def Selector(node_list):
        self.node_list = node_list;

    def Evaluate():
        isAnyNodeRunning = false

        for node in nodes:
            if node.Evaluate() == State.RUNNING:
                isAnyNodeRunning = true
                break
            elif node.Evaluate() == State.SUCCESS:
                break
            elif node.Evaluate() == State.FAILURE:
                _nodeState = State.FAILURE;
                break
            else:
                break

            _nodeState = State.FAILURE
            return _nodeState

        if isAnyNodeRunning:
            _nodeState = State.RUNNING
        else:
            _nodeState = State.SUCCESS

        return _nodeState
