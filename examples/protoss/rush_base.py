from sc2 import maps
from sc2.bot_ai import BotAI
from sc2.data import Difficulty, Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.main import run_game
from sc2.player import Bot, Computer

import py_trees
import random

class FastBaseBot(BotAI):

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

        # Build GATEWAY and CYBERNETICSCORE when pylon is built
        if self.structures(UnitTypeId.PYLON).ready + self.already_pending(UnitTypeId.NEXUS) > 1 + self.townhalls.ready.amount = :
            proxy = self.structures(UnitTypeId.PYLON).closest_to(self.enemy_start_locations[0])
            pylon = self.structures(UnitTypeId.PYLON).ready.random
            if self.structures(UnitTypeId.GATEWAY).ready:
                # If we have no cyber core, build one
                if not self.structures(UnitTypeId.CYBERNETICSCORE):
                    if (
                        self.can_afford(UnitTypeId.CYBERNETICSCORE)
                        and self.already_pending(UnitTypeId.CYBERNETICSCORE) == 0
                    ):
                        await self.build(UnitTypeId.CYBERNETICSCORE, near=pylon)
            # Build up to 2 gates
            if (
                self.can_afford(UnitTypeId.GATEWAY)
                and self.structures(UnitTypeId.WARPGATE).amount + self.structures(UnitTypeId.GATEWAY).amount < 2
            ):
                await self.build(UnitTypeId.GATEWAY, near=pylon)



def main():
    run_game(
        maps.get("BerlingradAIE"),
        [Bot(Race.Protoss, FastBaseBot()),
         Computer(Race.Protoss, Difficulty.Easy)],
        realtime=False,
    )


if __name__ == "__main__":
    main()
