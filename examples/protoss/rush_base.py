from sc2 import maps
from sc2.bot_ai import BotAI
from sc2.data import Difficulty, Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.main import run_game
from sc2.player import Bot, Computer

from abc import ABC, abstractmethod
from enum import Enum, auto
from time import sleep

class State(Enum):
    RUNNING = auto()
    SUCCESS = auto()
    FAILURE = auto()

class FastBaseBot(BotAI):
    def __init__(self):
        army = BTNode()
        self.army = army

    # pylint: disable=R0912
    async def on_step(self, iteration):
        target_base_count = 3
        target_stargate_count = 3

        if iteration == 0:
            await self.chat_send("(glhf)")

        if not self.townhalls.ready:
            # Attack with all workers if we don't have any nexuses left, attack-move on enemy spawn (doesn't work on 4 player map) so that probes auto attack on the way
            for worker in self.workers:
                worker.attack(self.enemy_start_locations[0])
            return

        nexus = self.townhalls.ready.random
        # Distribute workers in gas and across bases
        await self.distribute_workers()

        # If this random nexus is not idle and has not chrono buff, chrono it with one of the nexuses we have
        if not nexus.is_idle and not nexus.has_buff(BuffId.CHRONOBOOSTENERGYCOST):
            nexuses = self.structures(UnitTypeId.NEXUS)
            abilities = await self.get_available_abilities(nexuses)
            for loop_nexus, abilities_nexus in zip(nexuses, abilities):
                if AbilityId.EFFECT_CHRONOBOOSTENERGYCOST in abilities_nexus:
                    loop_nexus(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, nexus)
                    break

        # If we are low on supply, build pylon near next nexus expansion site
        if (
            self.supply_left < 2 and self.already_pending(UnitTypeId.PYLON) == 0
            or self.supply_used > 15 and self.supply_left < 4 and self.already_pending(UnitTypeId.PYLON) < 2
        ):
            # Always check if you can afford something before you build it
            if self.can_afford(UnitTypeId.PYLON):
                location = await self.get_next_expansion()
                position = await self.find_placement(UnitTypeId.PYLON, near=location)

                await self.build(UnitTypeId.PYLON, near=position)

        # Train probe on nexuses that are undersaturated (avoiding distribute workers functions)
        # if nexus.assigned_harvesters < nexus.ideal_harvesters and nexus.is_idle:
        if self.supply_workers + self.already_pending(UnitTypeId.PROBE) < self.townhalls.amount * 22 and nexus.is_idle:
            if self.can_afford(UnitTypeId.PROBE):
                nexus.train(UnitTypeId.PROBE)

        # If we have less than 2 nexuses and none pending yet, expand
        if self.townhalls.ready.amount + self.already_pending(UnitTypeId.NEXUS) < 2:
            if self.can_afford(UnitTypeId.NEXUS):
                await self.expand_now()

        # Build gas
        if self.townhalls.ready.amount + self.already_pending(UnitTypeId.NEXUS) > 1:
            for nexus in self.townhalls.ready:
                vgs = self.vespene_geyser.closer_than(15, nexus)
                for vg in vgs:
                    if not self.can_afford(UnitTypeId.ASSIMILATOR):
                        break
                    worker = self.select_build_worker(vg.position)
                    if worker is None:
                        break
                    if not self.gas_buildings or not self.gas_buildings.closer_than(1, vg):
                        worker.build_gas(vg)
                        worker.stop(queue=True)






        class BehaviorTree():
            scout = scoutMap(self.game_info, self.units())

            kite = kiteEnemy(self.game_info, self.units())

            attack = attackEnemy(self.game_info, self.units())

            #flee = fleeEnemy()


            armySequence = Sequence( [scout, kite, attack] )
            #print([checkTwoSecond.Evaluate(), checkThreeSecond.Evaluate()])
            armySequence.Evaluate()


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


class Sequence(BTNode):
    print("IN Sequence")
    def __init__(self, nodes):
        self.node_list = nodes;

    def Sequence(node_list):
        self.node_list = node_list;

    def Evaluate(self):
        isAnyNodeRunning = False
        #for node in self.node_list:
        i = 0
        while i < len(self.node_list):
            node = self.node_list[i]
            node._nodeState = node.Evaluate()

            # Evaluate next node/behaviour if first behaviour is SUCCESS
            if node._nodeState == State.SUCCESS:
                self.node_list[i].Evaluate()
                i += 1
                continue
            # Continue evaluating this behaviour otherwise
            else:
                node._nodeState = node.Evaluate()

        if isAnyNodeRunning:
            _nodeState = State.RUNNING
        else:
            _nodeState = State.SUCCESS

        return _nodeState



class scoutMap(BTNode):
    def __init__(self, game_info, units):
        self._game_info = game_info
        self.units = units

    # I want to return the unit who entered our vision together with a boolean
    def on_enemy_unit_entered_vision(self, unit: Unit): ### This does not work
        return True, self.unit

    def Evaluate(self):
        if self.units().amount > 1:
            for unit in self.units():
                unit.move(self._game_info.map_center)

        seen_enemy, unit = self.on_enemy_unit_entered_vision()
        if seen_enemy:
            self._nodeState = State.SUCCESS
            return State.SUCCESS

        self._nodeState = State.FAILURE
        return State.FAILURE


class kiteEnemy(BTNode):
    def __init__(self, game_info, units):
        self._game_info = game_info
        self.units = units

    def on_enemy_unit_entered_vision(self, unit: Unit):
        return True, unit

    def Evaluate(self):
        # Find the closest enemy
        enemyUnits = self.enemy_units.closer_than(5, r) # hardcoded attack range of 5
        enemyUnits = enemyUnits.sorted(lambda x: x.distance_to(r))
        closestEnemy = enemyUnits[0]

        seen_enemy, unit = self.on_enemy_unit_entered_vision()
        # If the enemy is a ranged unit, we cannot KITE -> Go to next behaviour in the Sequence
        if unit(UnitTypeId.VOIDRAY) or unit(UnitTypeId.STALKER):
            self._nodeState = State.SUCCESS
            return State.SUCCESS
        # Else: Keep distance and continue to attack
        else:
            for unit in self.units():
                # If we have stalkers, use them to KITE
                if unit(UnitTypeId.STALKER):
                    if _distance_squared_unit_to_unit_method0(unit,enemy) < 20:
                        # Move away from enemy
                        unit.move(self._game_info.map_center.towards(self._game_info.start_location, random.randrange(8, 15))) ### THIS LINE IS WRONG
                    else:
                        unit.attack(closestEnemy)

                    self._nodeState = State.FAILURE
                    return State.FAILURE
                # If we do not have stalkers, we cannot KITE  -> Go to next behaviour in the Sequence
                else:
                    self._nodeState = State.SUCCESS
                    return State.SUCCESS


class attackEnemy(BTNode):
    def __init__(self, game_info, units):
        self._game_info = game_info
        self.units = units

    def Evaluate(self, units):
        enemy = self.on_enemy_unit_entered_vision()
        for unit in self.units():
            unit.attack(enemy)

        return State.FAILURE

#class fleeEnemy():




def main():
    run_game(
        maps.get("BerlingradAIE"),
        [Bot(Race.Protoss, FastBaseBot()),
         Computer(Race.Protoss, Difficulty.Easy)],
        realtime=False,
    )


if __name__ == "__main__":
    main()
