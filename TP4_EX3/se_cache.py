# -*- coding: utf-8 -*-
#!/usr/bin/env python3
# se_cache.py gem5 SE script avec hierarchies de caches C1/C2 (L1I/L1D/L2) + line size.
#
# C1:
#   L1I 4kB DM, L1D 4kB DM, L2 32kB DM, line=32B
# C2:
#   L1I 4kB DM, L1D 4kB 2-way, L2 32kB 4-way, line=32B
#
# Exemple:
#   build/RISCV/gem5.opt -d m5out_P1_C1 configs/se_cache.py --cmd=./P1.riscv --conf=C1
#   build/RISCV/gem5.opt -d m5out_P1_C2 configs/se_cache.py --cmd=./P1.riscv --conf=C2
#
# Stats a extraire:
#   grep -E "icache.*MissRate|dcache.*MissRate|l2cache.*MissRate" m5out_*/stats.txt

import argparse
import m5
from m5.objects import (
    System, SrcClockDomain, VoltageDomain,
    AddrRange, SystemXBar, L2XBar,
    Process, SEWorkload, Root,
    MemCtrl, DDR3_1600_8x8,
    Cache, DerivO3CPU, TimingSimpleCPU,
)

# ------------------ Caches (classiques) ------------------

class L1ICache(Cache):
    assoc = 1
    tag_latency = 2
    data_latency = 2
    response_latency = 2
    mshrs = 4
    tgts_per_mshr = 8
    is_read_only = True
    writeback_clean = True

    def connectCPU(self, cpu):
        self.cpu_side = cpu.icache_port

    def connectBus(self, bus):
        self.mem_side = bus.cpu_side_ports


class L1DCache(Cache):
    assoc = 1
    tag_latency = 2
    data_latency = 2
    response_latency = 2
    mshrs = 8
    tgts_per_mshr = 8
    writeback_clean = True

    def connectCPU(self, cpu):
        self.cpu_side = cpu.dcache_port

    def connectBus(self, bus):
        self.mem_side = bus.cpu_side_ports


class L2Cache(Cache):
    assoc = 1
    tag_latency = 10
    data_latency = 10
    response_latency = 10
    mshrs = 16
    tgts_per_mshr = 12
    writeback_clean = True

    def connectCPUSideBus(self, bus):
        self.cpu_side = bus.mem_side_ports

    def connectMemSideBus(self, bus):
        self.mem_side = bus.cpu_side_ports


# ------------------ Helpers ------------------

def apply_cache_conf(args, system):
    """
    Cree I$, D$, L2 selon C1/C2 ou selon parametres custom.
    """
    system.cache_line_size = args.line_size

    # Selection config
    if args.conf == "C1":
        l1i_size, l1i_assoc = "4kB", 1
        l1d_size, l1d_assoc = "4kB", 1
        l2_size,  l2_assoc  = "32kB", 1
    elif args.conf == "C2":
        l1i_size, l1i_assoc = "4kB", 1
        l1d_size, l1d_assoc = "4kB", 2
        l2_size,  l2_assoc  = "32kB", 4
    else:
        # CUSTOM
        l1i_size, l1i_assoc = args.l1i_size, args.l1i_assoc
        l1d_size, l1d_assoc = args.l1d_size, args.l1d_assoc
        l2_size,  l2_assoc  = args.l2_size,  args.l2_assoc

    # L1
    system.cpu.icache = L1ICache()
    system.cpu.dcache = L1DCache()
    system.cpu.icache.size = l1i_size
    system.cpu.icache.assoc = l1i_assoc
    system.cpu.dcache.size = l1d_size
    system.cpu.dcache.assoc = l1d_assoc

    # Bus L1 <-> L2
    system.l2bus = L2XBar()

    system.cpu.icache.connectCPU(system.cpu)
    system.cpu.dcache.connectCPU(system.cpu)
    system.cpu.icache.connectBus(system.l2bus)
    system.cpu.dcache.connectBus(system.l2bus)

    # L2
    system.l2cache = L2Cache()
    system.l2cache.size = l2_size
    system.l2cache.assoc = l2_assoc
    system.l2cache.connectCPUSideBus(system.l2bus)

    # Mem bus
    system.membus = SystemXBar()
    system.l2cache.connectMemSideBus(system.membus)

    # Ports systeme
    system.system_port = system.membus.cpu_side_ports


def build_system(args):
    system = System()

    system.clk_domain = SrcClockDomain()
    system.clk_domain.clock = args.clock
    system.clk_domain.voltage_domain = VoltageDomain()

    system.mem_mode = "timing"
    system.mem_ranges = [AddrRange(args.mem_size)]

    # CPU
    if args.cpu_type == "o3":
        system.cpu = DerivO3CPU()
    elif args.cpu_type == "timing":
        system.cpu = TimingSimpleCPU()
    else:
        raise ValueError("--cpu-type doit etre 'o3' ou 'timing'")

    # Caches
    if args.caches:
        apply_cache_conf(args, system)
    else:
        system.membus = SystemXBar()
        system.system_port = system.membus.cpu_side_ports
        system.cpu.icache_port = system.membus.cpu_side_ports
        system.cpu.dcache_port = system.membus.cpu_side_ports

    # Memoire
    system.mem_ctrl = MemCtrl()
    system.mem_ctrl.dram = DDR3_1600_8x8()
    system.mem_ctrl.dram.range = system.mem_ranges[0]
    system.mem_ctrl.port = system.membus.mem_side_ports

    # Workload SE
    process = Process()
    process.cmd = [args.cmd] + args.options
    system.workload = SEWorkload.init_compatible(args.cmd)
    system.cpu.workload = process
    system.cpu.createThreads()

    # Interrupts / TLB walkers (selon ISA, utile en RISC-V)
    system.cpu.createInterruptController()

    return system


def parse_args():
    ap = argparse.ArgumentParser()

    ap.add_argument("--cmd", required=True, help="Binaire a executer (RISC-V ou autre selon build)")
    ap.add_argument("--options", nargs=argparse.REMAINDER, default=[], help="Arguments passes au binaire")

    ap.add_argument("--cpu-type", default="o3", choices=["o3", "timing"])
    ap.add_argument("--clock", default="2GHz")
    ap.add_argument("--mem-size", default="2GB")

    ap.add_argument("--caches", action="store_true", help="Active L1I/L1D/L2")
    ap.add_argument("--line-size", type=int, default=32)

    ap.add_argument("--conf", default="C1", choices=["C1", "C2", "CUSTOM"],
                    help="Choix config cache. CUSTOM utilise les parametres ci-dessous.")

    ap.add_argument("--l1i-size", default="4kB")
    ap.add_argument("--l1i-assoc", type=int, default=1)
    ap.add_argument("--l1d-size", default="4kB")
    ap.add_argument("--l1d-assoc", type=int, default=1)
    ap.add_argument("--l2-size", default="32kB")
    ap.add_argument("--l2-assoc", type=int, default=1)

    ap.add_argument("--maxinsts", type=int, default=0,
                    help="Stop apres N instructions (0 = pas de limite)")

    return ap.parse_args()


def main():
    args = parse_args()
    system = build_system(args)

    root = Root(full_system=False, system=system)
    m5.instantiate()

    if args.maxinsts and args.maxinsts > 0:
        exit_event = m5.simulate(args.maxinsts)
    else:
        exit_event = m5.simulate()

    m5.stats.dump()
    m5.stats.reset()


    print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")


main()

