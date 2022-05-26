from sc2 import maps
from sc2.bot_ai import BotAI
from sc2.data import Difficulty, Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.upgrade_id import UpgradeId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.main import run_game
from sc2.player import Bot, Computer
import random 
from sc2.position import Point2
from loguru import logger
from threebase_voidray import ThreebaseVoidrayBot

class Brotoss(BotAI):
    scouting_workers = []
    first_scout = True
    def __init__(self):
        super().__init__()
        self.scouting_workers = []
        self.first_scout = True
        self.scout_harassment_target = None
        self.strategy = "StalkerPush" #VoidrayRush/Stalkerpush/Immortals/DarkTemplar/Tempest

    async def scout(self):
        #We retrieve the list of possible extensions
        self.ordered_expansions = None
        self.ordered_expansions = sorted(
            self.expansion_locations_dict.keys(), key=lambda expansion: expansion.distance_to(self.enemy_start_locations[0])
        )
        if(len(self.scouting_workers) > 0):
            # removing of dead scouting_workers
            to_be_removed = []
            existing_ids = [unit.tag for unit in self.units]
            to_be_removed = []
            for noted_scout in self.scouting_workers:
                if noted_scout.tag not in existing_ids:
                    to_be_removed.append(noted_scout)
            for scout in to_be_removed:
                self.scouting_workers.remove(scout)

        if(len(self.scouting_workers) == 0):
            if(self.first_scout):
                for obs in self.units(UnitTypeId.PROBE):
                    self.scouting_workers.append(obs)
                    self.first_scout = False
                    obs.move(self.ordered_expansions[0])
                    break   

        #We send the scouting_workers			
        for obs in self.scouting_workers:
            #logger.info(f"scout: {obs.position_tuple}")
            escape_location = obs.position.towards(self.start_location, 6)
            enemies: Units = self.enemy_units | self.enemy_structures
            enemies2 = self.enemy_units.filter(lambda unit: unit.type_id not in {UnitTypeId.DRONE,UnitTypeId.PROBE})
            enemies_can_attack: Units = enemies2.filter(lambda unit: unit.can_attack_ground)
            enemyThreatsClose: Units = enemies_can_attack.filter(lambda unit: unit.distance_to(obs) < 555)  # Threats that can attack the scout
            if enemyThreatsClose:
                retreatPoints = self.around8(obs.position, distance=10) | self.around8(obs.position, distance=14)
                # Filter points that are pathable
                retreatPoints = {x for x in retreatPoints if self.in_pathing_grid(x)}
                if retreatPoints:
                    closestEnemy: Unit = enemyThreatsClose.closest_to(obs)
                    retreatPoint: Unit = closestEnemy.position.furthest(retreatPoints)
                    obs.move(retreatPoint)
                    continue

            elif(obs.distance_to(self.ordered_expansions[0])>300 and obs.shield_percentage>=0.80):
                #logger.info(f"shieldperc: {obs.shield_percentage}")
                obs.move(self.ordered_expansions[0])
            else:
                probes = self.enemy_units.filter(lambda unit: unit.type_id in {UnitTypeId.PROBE})
                
                if(len(probes)>0):
                    if(self.scout_harassment_target != None):
                        if(self.scout_harassment_target not in self.enemy_units.filter(lambda unit: unit.type_id in {UnitTypeId.PROBE})):
                            self.scout_harassment_target = None
                    if(self.scout_harassment_target == None):
                        #obs.attack(probes.closest_to(obs))
                        self.scout_harassment_target = probes.closest_to(obs)
                    else:
                        obs.attack(self.scout_harassment_target)
                    if(obs.shield_percentage<0.80):
                        #logger.info(f"shieldperc: {obs.shield_percentage}")
                        obs.move(escape_location)
                else:
                    #logger.info(f"shieldperc: {obs.shield_percentage}")
                    pylons = self.enemy_structures.filter(lambda structure: structure.type_id in {UnitTypeId.PYLON})
                    
                    if(len(pylons)>0):
                        #Can throw an error right after the scout gets destroyed
                        if(not obs.is_attacking and self.scout_harassment_target == None):
                            #obs.attack(pylons.closest_to(obs))
                            pass
                        #obs.attack(probes.closest_to(obs))

            ### Current Problem: Probe gets attacked by computer enemy before even attacking the pylon: move to pylon first-> then attack
                
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
        # If this random nexus is not idle and has not chrono buff, chrono it with one of the nexuses we have
        if not nexus.is_idle and not nexus.has_buff(BuffId.CHRONOBOOSTENERGYCOST):
            nexuses = self.structures(UnitTypeId.NEXUS)
            abilities = await self.get_available_abilities(nexuses)
            for loop_nexus, abilities_nexus in zip(nexuses, abilities):
                if AbilityId.EFFECT_CHRONOBOOSTENERGYCOST in abilities_nexus:
                    loop_nexus(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, nexus)
                    break

        #VOIDRAY RUSH
        # If we have at least 5 void rays, attack closes enemy unit/building, or if none is visible: attack move towards enemy spawn
        #await self.VRR()
        
        #SCOUT HARASSMENT
        #await self.scout()
        # Distribute workers in gas and across bases
        await self.distribute_workers()

        # If we are low on supply, build pylon
        if (
            self.supply_left < 2 and self.already_pending(UnitTypeId.PYLON) == 0
            or self.supply_used > 25 and self.supply_left < 4 and self.already_pending(UnitTypeId.PYLON) < 2
        ):
            # Always check if you can afford something before you build it
            if self.can_afford(UnitTypeId.PYLON):
                await self.build(UnitTypeId.PYLON, near=nexus)

        # Train probe on nexuses that are undersaturated (avoiding distribute workers functions)
        # if nexus.assigned_harvesters < nexus.ideal_harvesters and nexus.is_idle:
        if self.supply_workers + self.already_pending(UnitTypeId.PROBE) < self.townhalls.amount * 23 and nexus.is_idle:
            if self.can_afford(UnitTypeId.PROBE):
                nexus.train(UnitTypeId.PROBE)

        #Are three nexuses necessary? or should the third be considered later
        # If we have less than 3 nexuses and none pending yet, expand
        if self.townhalls.ready.amount + self.already_pending(UnitTypeId.NEXUS) < 3:
            if self.can_afford(UnitTypeId.NEXUS):
                await self.expand_now()

        if(self.strategy == "StalkerPush"):
            #Pylon -> Gateway -> Gateway
            await self.buildorder3Warpgate()
            #gets 6 stalkers ready
            await self.STPRecruitment()
            await self.STP()
        elif(self.strategy == "VoidrayRush"):
            #Pylon -> Gateway -> CyberneticsCore
            await self.buildorderCybernetics()
            #Builds 3 stargates for the voidRayRush - requires warpgate,cyberneticscore and gas
            await self.VRRstargateConstruction(target_base_count,target_stargate_count)
            #builds voidrays only if 3 nexuses are ready
            await self.VRRvoidrayRecruitment()
            await self.VRR()

    #strategy functions
    async def VRRstargateConstruction(self,target_base_count,target_stargate_count):
        #Builds 3 stargates for the voidRayRush - requires warpgate,cyberneticscore and gas
        # If we have less than 3  but at least 3 nexuses, build stargate
        if self.structures(UnitTypeId.PYLON).ready and self.structures(UnitTypeId.CYBERNETICSCORE).ready:
            pylon = self.structures(UnitTypeId.PYLON).ready.random
            if (
                self.townhalls.ready.amount + self.already_pending(UnitTypeId.NEXUS) >= target_base_count
                and self.structures(UnitTypeId.STARGATE).ready.amount + self.already_pending(UnitTypeId.STARGATE) <
                target_stargate_count
            ):
                if self.can_afford(UnitTypeId.STARGATE):
                    await self.build(UnitTypeId.STARGATE, near=pylon)
    async def VRRvoidrayRecruitment(self):
        #builds voidrays only if 3 nexuses are ready
        # Save up for expansions, loop over idle completed stargates and queue void ray if we can afford
        if self.townhalls.amount >= 3:
            for sg in self.structures(UnitTypeId.STARGATE).ready.idle:
                if self.can_afford(UnitTypeId.VOIDRAY):
                    sg.train(UnitTypeId.VOIDRAY)
    
    async def buildorderCybernetics(self):
        #Basic build-order till cybernetics core
        # Once we have a pylon completed
        if self.structures(UnitTypeId.PYLON).ready:
            pylon = self.structures(UnitTypeId.PYLON).ready.random
            if self.structures(UnitTypeId.GATEWAY).ready:
                # If we have gateway completed, build cyber core
                if not self.structures(UnitTypeId.CYBERNETICSCORE):
                    if (
                        self.can_afford(UnitTypeId.CYBERNETICSCORE)
                        and self.already_pending(UnitTypeId.CYBERNETICSCORE) == 0
                    ):
                        await self.build(UnitTypeId.CYBERNETICSCORE, near=pylon)
            else:
                # If we have no gateway, build gateway
                if self.can_afford(UnitTypeId.GATEWAY) and self.already_pending(UnitTypeId.GATEWAY) == 0:
                    await self.build(UnitTypeId.GATEWAY, near=pylon)
        # Build gas near completed nexuses once we have a cybercore (does not need to be completed
        if self.structures(UnitTypeId.CYBERNETICSCORE):
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
    async def buildorder3Warpgate(self):
        #Basic build-order for a 3 warpgate push with stalkers
        # Once we have a pylon completed
        if self.structures(UnitTypeId.PYLON).ready:
            pylon = self.structures(UnitTypeId.PYLON).ready.random
            if self.structures(UnitTypeId.GATEWAY).ready or self.structures(UnitTypeId.WARPGATE).ready:
                # If we have gateway completed and started gas production, build another one
                if not len(self.structures(UnitTypeId.GATEWAY))+len(self.structures(UnitTypeId.WARPGATE))>1 and len(self.structures(UnitTypeId.ASSIMILATOR))>=2:
                    if (
                        self.can_afford(UnitTypeId.GATEWAY)
                        and self.already_pending(UnitTypeId.GATEWAY) == 0
                    ):
                        await self.build(UnitTypeId.GATEWAY, near=pylon)
                # If we have 2gateways completed, build a cybernetics core
                if len(self.structures(UnitTypeId.GATEWAY))+len(self.structures(UnitTypeId.WARPGATE))==2 and not self.structures(UnitTypeId.CYBERNETICSCORE):
                    if (
                        self.can_afford(UnitTypeId.CYBERNETICSCORE)
                        and self.already_pending(UnitTypeId.CYBERNETICSCORE) == 0
                    ):
                        await self.build(UnitTypeId.CYBERNETICSCORE, near=pylon)
                elif(self.structures(UnitTypeId.CYBERNETICSCORE)):
                    self.warpgate_research()

            else:
                # If we have no gateway, build gateway
                if self.can_afford(UnitTypeId.GATEWAY) and self.already_pending(UnitTypeId.GATEWAY) == 0:
                    await self.build(UnitTypeId.GATEWAY, near=pylon)
        
        # Build gas near completed nexuses once we have a warpgate (does not need to be completed
        if self.structures(UnitTypeId.GATEWAY) or self.structures(UnitTypeId.WARPGATE):
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
    async def STPRecruitment(self):
        #builds stalkers once we have 2 warpgates and a cybercore
        if len(self.structures(UnitTypeId.GATEWAY))+len(self.structures(UnitTypeId.WARPGATE)) >= 2 and len(self.units(UnitTypeId.STALKER))<9:
            for sg in self.structures(UnitTypeId.GATEWAY).ready.idle:
                if self.can_afford(UnitTypeId.STALKER):
                    sg.train(UnitTypeId.STALKER)
            await self.warp_new_units()
    async def VRR(self):
        # If we have at least 5 void rays, attack closes enemy unit/building, or if none is visible: attack move towards enemy spawn
        if self.units(UnitTypeId.VOIDRAY).amount > 5:
            for vr in self.units(UnitTypeId.VOIDRAY):
                # Activate charge ability if the void ray just attacked
                if vr.weapon_cooldown > 0:
                    vr(AbilityId.EFFECT_VOIDRAYPRISMATICALIGNMENT)
                # Choose target and attack, filter out invisible targets
                targets = (self.enemy_units | self.enemy_structures).filter(lambda unit: unit.can_be_attacked)
                if targets:
                    target = targets.closest_to(vr)
                    vr.attack(target)
                else:
                    vr.attack(self.enemy_start_locations[0])
    async def STP(self):
        # If we have at least 6 stalkers, attack closes enemy unit/building, or if none is visible: attack move towards enemy spawn
        if self.units(UnitTypeId.STALKER).amount > 5:
            for vr in self.units(UnitTypeId.STALKER):
                # Choose target and attack, filter out invisible targets
                enemies: Units = self.enemy_units | self.enemy_structures
                enemies2 = self.enemy_units.filter(lambda unit: unit.type_id in {UnitTypeId.DRONE,UnitTypeId.PROBE,UnitTypeId.PYLON})
                #targets = (self.enemy_units | self.enemy_structures).filter(lambda unit: unit.can_be_attacked)
                if enemies2:
                    target = enemies2.closest_to(vr)
                    vr.attack(target)
                else:
                    vr.attack(self.enemy_start_locations[0])

    #method to research warpgate, if CC ready, and can afford and not yet researched
    def warpgate_research(self):
        if (
            self.structures(UnitTypeId.CYBERNETICSCORE).ready
            and self.can_afford(AbilityId.RESEARCH_WARPGATE)
            and self.already_pending_upgrade(UpgradeId.WARPGATERESEARCH) == 0
        ):
        #We research warp gate ! 
            ccore = self.structures(UnitTypeId.CYBERNETICSCORE).ready.first
            ccore.research(UpgradeId.WARPGATERESEARCH)

    async def warp_new_units(self):
        for warpgate in self.structures(UnitTypeId.WARPGATE).ready:
            #We take the abilities of the warpgate to retrieves the warping stalker ability
            abilities = await self.get_available_abilities(warpgate)
            #if it is not on cooldown
            if AbilityId.WARPGATETRAIN_STALKER in abilities:
                #we sort the pylons by their distance to our warp gate
                self.ordered_pylons = sorted(self.structures(UnitTypeId.PYLON).ready, key=lambda pylon: pylon.distance_to(warpgate))
                #we pick the pylon the further away from the warp gate, because why not
                pos = self.ordered_pylons[-1].position.random_on_distance(4)
                #we select the placement of the stalker we want to warp as the position of the pylon selected 
                placement = await self.find_placement(AbilityId.WARPGATETRAIN_STALKER, pos, placement_step=1)
                #if no placement  available we return error
                if placement is None:
                    print("can't place")
                    return
                #else we warp our stalker ! 
                warpgate.warp_in(UnitTypeId.STALKER, placement)
    #Functions used for evasion behaviour
    def around8(self, position, distance=1):
            p = position
            d = distance
            return self.around4(position, distance) | {
                Point2((p.x - d, p.y - d)),
                Point2((p.x - d, p.y + d)),
                Point2((p.x + d, p.y - d)),
                Point2((p.x + d, p.y + d)),
            }
    def around4(self, position, distance=1):
        p = position
        d = distance
        return {Point2((p.x - d, p.y)), Point2((p.x + d, p.y)), Point2((p.x, p.y - d)), Point2((p.x, p.y + d))}
def main():
    run_game(
        maps.get("BerlingradAIE"),
        [Bot(Race.Protoss, Brotoss()),
         Bot(Race.Protoss, ThreebaseVoidrayBot())],
        realtime=True,
    )

if __name__ == "__main__":
    main()
