// PROTOTYPE (throwaway): three variants of the thread details "Host" section, mounted in
// ThreadDetailsPanel under Context. Switch with ?variant=A|B|C and the dataset with ?state=devbox|mac
// (floating bar, arrow keys cycle variants). Mock data only: no server change. Dev builds only.
import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { ChevronRightIcon } from "lucide-react";
import { createPortal } from "react-dom";

import { cn } from "../../lib/utils";
import { ThreadDetailsSection } from "./ThreadDetailsSection";

type Tone = "error" | "warning" | null;
const tone = (p: number): Tone => (p >= 90 ? "error" : p >= 80 ? "warning" : null);

interface MockHost {
  readonly model: string;
  /** Utilization per core; one entry per thread (devbox1: 2, Mac: 1). */
  readonly cores: readonly (readonly number[])[];
  /** Mac only: leading cores that are performance cores. */
  readonly perf?: number;
  readonly cpu: number;
  readonly memUsed: number;
  readonly memTotal: number;
  readonly diskUsed: number;
  readonly diskTotal: number;
}

const GIB = 1024 ** 3;
const MOCKS: Record<"devbox" | "mac", MockHost> = {
  devbox: {
    model: "AMD Ryzen 7",
    cores: [[18, 12], [9, 6], [14, 8], [96, 71], [22, 31], [5, 3], [11, 17], [7, 4]],
    cpu: 22,
    memUsed: 19.0 * GIB,
    memTotal: 29.4 * GIB,
    diskUsed: 330 * GIB,
    diskTotal: 936 * GIB,
  },
  mac: {
    model: "Apple M-series",
    cores: [[62], [48], [35], [40], [12], [9], [6], [14], [4], [8]],
    perf: 4,
    cpu: 31,
    memUsed: 11.2 * GIB,
    memTotal: 16 * GIB,
    diskUsed: 262 * GIB,
    diskTotal: 460 * GIB,
  },
};

const VARIANTS = [
  { key: "A", name: "Core cells" },
  { key: "B", name: "Thread bars" },
  { key: "C", name: "Expandable rows" },
] as const;
type VariantKey = (typeof VARIANTS)[number]["key"];
const DATASETS = ["devbox", "mac"] as const;
type Dataset = (typeof DATASETS)[number];

const listeners = new Set<() => void>();
function subscribe(cb: () => void) {
  listeners.add(cb);
  window.addEventListener("popstate", cb);
  return () => {
    listeners.delete(cb);
    window.removeEventListener("popstate", cb);
  };
}
const snapshot = () => window.location.search;
function setParam(name: string, value: string) {
  const url = new URL(window.location.href);
  url.searchParams.set(name, value);
  window.history.replaceState(window.history.state, "", url);
  listeners.forEach((cb) => cb());
}
function usePrototypeParams() {
  const search = useSyncExternalStore(subscribe, snapshot, () => "");
  const params = new URLSearchParams(search);
  const variant = (VARIANTS.find((v) => v.key === params.get("variant"))?.key ?? "A") as VariantKey;
  const dataset = (DATASETS.find((d) => d === params.get("state")) ?? "devbox") as Dataset;
  return { variant, dataset };
}

const gib = (bytes: number) => (bytes / GIB).toFixed(bytes / GIB < 100 ? 1 : 0);
const barFill = (t: Tone) =>
  t === "error" ? "bg-error" : t === "warning" ? "bg-warning" : "bg-foreground/80";
const valueTone = (t: Tone) =>
  t === "error" ? "text-error-foreground" : t === "warning" ? "text-warning-foreground" : "text-foreground/80";

function HostRow(props: { label: React.ReactNode; fill: number; value: string; onClick?: () => void }) {
  const t = tone(props.fill);
  return (
    <div
      tabIndex={0}
      onClick={props.onClick}
      className={cn(
        "col-span-3 grid h-6 cursor-default grid-cols-subgrid items-center rounded-lg px-2.5 outline-none hover:bg-black/[0.035] focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring dark:hover:bg-white/[0.08]",
        props.onClick && "cursor-pointer",
      )}
    >
      <span className="flex max-w-28 items-center truncate text-muted-foreground">{props.label}</span>
      <Bar fill={props.fill} />
      <span className={cn("text-end font-medium tabular-nums", valueTone(t))}>{props.value}</span>
    </div>
  );
}

function Bar({ fill, thin = false }: { fill: number; thin?: boolean }) {
  return (
    <span
      className={cn(
        "relative rounded-full bg-muted-foreground/30 dark:bg-muted-foreground/20",
        thin ? "h-[2px]" : "h-[3px]",
      )}
    >
      <span
        className={cn("absolute inset-y-0 left-0 rounded-full", barFill(tone(fill)))}
        style={{ width: `max(${fill}%, 4px)` }}
      />
    </span>
  );
}

const pct = (used: number, total: number) => Math.round((used / total) * 100);
const smt = (h: MockHost) => (h.cores[0]?.length ?? 1) > 1;
const topology = (h: MockHost) =>
  smt(h)
    ? `${h.model} · ${h.cores.length} cores · ${h.cores.length * 2} threads`
    : `${h.model} · ${h.cores.length} cores (${h.perf} P + ${h.cores.length - (h.perf ?? 0)} E)`;

function MemoryDisk({ h }: { h: MockHost }) {
  return (
    <>
      <HostRow label="Memory" fill={pct(h.memUsed, h.memTotal)} value={`${gib(h.memUsed)} / ${gib(h.memTotal)} GiB`} />
      <HostRow label="Disk" fill={pct(h.diskUsed, h.diskTotal)} value={`${gib(h.diskUsed)} / ${gib(h.diskTotal)} GB`} />
    </>
  );
}

const GRID = "grid grid-cols-[auto_minmax(3rem,1fr)_auto] gap-x-3 text-xs";
const CAPTION = "px-2.5 pt-0.5 text-[10px] text-muted-foreground tabular-nums";
const heat = (p: number) => cn("absolute inset-x-0 bottom-0", p >= 80 ? barFill(tone(p)) : "bg-foreground/70");

/** A: summary bars, then one cell per core, split in one half per thread. */
function VariantA({ h }: { h: MockHost }) {
  const cell = (c: readonly number[], i: number) => (
    <div
      key={i}
      title={`Core ${i + 1}: ${c.map((p) => `${p}%`).join(" / ")}`}
      className={cn("grid h-6 gap-px overflow-hidden rounded-[5px] bg-border", c.length > 1 ? "grid-cols-2" : "grid-cols-1")}
    >
      {c.map((p, t) => (
        <span key={t} className="relative bg-muted-foreground/25">
          <span className={heat(p)} style={{ height: `${Math.max(p, 5)}%` }} />
        </span>
      ))}
    </div>
  );
  const row = (cores: readonly (readonly number[])[], offset: number, label?: string) => (
    <>
      {label ? <div className="px-2.5 pt-1.5 text-[10px] text-muted-foreground">{label}</div> : null}
      <div className="grid gap-1 px-2.5 pt-1.5" style={{ gridTemplateColumns: `repeat(${cores.length}, minmax(0, 1fr))` }}>
        {cores.map((c, i) => cell(c, offset + i))}
      </div>
    </>
  );
  const perf = h.perf ?? 0;
  return (
    <>
      <div className={GRID}>
        <HostRow label="CPU" fill={h.cpu} value={`${h.cpu}%`} />
        <MemoryDisk h={h} />
      </div>
      <div className={CAPTION}>
        {topology(h)}
        {smt(h) ? " · a cell is a core, its halves are its threads" : ""}
      </div>
      {h.perf ? (
        <>
          {row(h.cores.slice(0, perf), 0, "P-cores")}
          {row(h.cores.slice(perf), perf, "E-cores")}
        </>
      ) : (
        row(h.cores, 0)
      )}
    </>
  );
}

/** B: summary bars, then a thread bar chart; the two threads of a core sit together, cores are spaced apart. */
function VariantB({ h }: { h: MockHost }) {
  const perf = h.perf ?? 0;
  const col = (p: number, i: number) => (
    <span key={i} className="relative h-full w-[5px] overflow-hidden rounded-[2px] bg-muted-foreground/25">
      <span className={heat(p)} style={{ height: `${Math.max(p, 6)}%` }} />
    </span>
  );
  return (
    <>
      <div className={GRID}>
        <HostRow label="CPU" fill={h.cpu} value={`${h.cpu}%`} />
        <MemoryDisk h={h} />
      </div>
      <div className={CAPTION}>
        {topology(h)}
        {smt(h) ? " · adjacent bars are one core's threads" : ""}
      </div>
      <div className="flex h-11 items-end justify-between px-2.5 pt-2">
        {h.cores.map((c, i) => (
          <div key={i} className={cn("flex h-full items-end gap-[2px]", perf && i === perf && "ml-1.5 border-l border-border pl-3")}>
            {c.map(col)}
          </div>
        ))}
      </div>
      <div className="flex justify-between px-2.5 pt-0.5 text-[9px] text-muted-foreground tabular-nums">
        {h.cores.map((c, i) => (
          <span key={i} className={cn("text-center", perf && i === perf && "ml-1.5 pl-3")} style={{ width: c.length * 5 + (c.length - 1) * 2 }}>
            {i + 1}
          </span>
        ))}
      </div>
    </>
  );
}

/** C: summary only; the CPU row opens a per-core list, two thin bars per core. */
function VariantC({ h }: { h: MockHost }) {
  const [open, setOpen] = useState(true);
  const perf = h.perf ?? 0;
  return (
    <div className={GRID}>
      <HostRow
        onClick={() => setOpen((o) => !o)}
        label={
          <>
            <ChevronRightIcon aria-hidden className={cn("-ml-1 mr-0.5 size-3 transition-transform", open && "rotate-90")} />
            CPU
          </>
        }
        fill={h.cpu}
        value={`${h.cpu}%`}
      />
      {open ? (
        <div className="col-span-3">
          <div className={cn(CAPTION, "pl-6")}>
            {topology(h)}
            {smt(h) ? " · one bar per thread" : ""}
          </div>
          <div className="grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-1 py-1 pr-2.5 pl-6 text-[11px]">
            {h.cores.map((c, i) => (
              <div key={i} className="col-span-2 grid grid-cols-subgrid items-center">
                <span className="text-muted-foreground tabular-nums">{perf ? (i < perf ? `P${i + 1}` : `E${i - perf + 1}`) : `C${i + 1}`}</span>
                <span className="grid gap-[3px]">
                  {c.map((p, t) => (
                    <Bar key={t} fill={p} thin />
                  ))}
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
      <MemoryDisk h={h} />
    </div>
  );
}

export function ThreadDetailsHostPrototype() {
  const { variant, dataset } = usePrototypeParams();
  const h = MOCKS[dataset];
  return (
    <>
      <ThreadDetailsSection headingId="thread-details-host-heading" title="Host" showHeading={false}>
        <div key={`${variant}-${dataset}`}>
          {variant === "A" ? <VariantA h={h} /> : variant === "B" ? <VariantB h={h} /> : <VariantC h={h} />}
        </div>
      </ThreadDetailsSection>
      <PrototypeSwitcher variant={variant} dataset={dataset} />
    </>
  );
}

function PrototypeSwitcher({ variant, dataset }: { variant: VariantKey; dataset: Dataset }) {
  const index = VARIANTS.findIndex((v) => v.key === variant);
  const step = useCallback((d: number) => setParam("variant", VARIANTS[(index + d + VARIANTS.length) % VARIANTS.length]!.key), [index]);
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (el && (el.closest("input,textarea,[contenteditable='true']") || el.isContentEditable)) return;
      if (e.key === "ArrowLeft") step(-1);
      if (e.key === "ArrowRight") step(1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [step]);
  if (import.meta.env.PROD || !mounted) return null;
  const btn = "rounded-full px-2 py-1 hover:bg-white/15 dark:hover:bg-black/10";
  return createPortal(
    <div
      data-prototype-switcher
      className="fixed bottom-3 left-1/2 z-[1000] flex -translate-x-1/2 items-center gap-2 rounded-full bg-neutral-900 px-3 py-1.5 text-xs text-white shadow-lg ring-1 ring-white/20 max-sm:bottom-1/2 max-sm:left-2 max-sm:translate-x-0 max-sm:translate-y-1/2 max-sm:flex-col dark:bg-neutral-100 dark:text-neutral-900"
    >
      <button type="button" aria-label="Previous variant" className={btn} onClick={() => step(-1)}>←</button>
      <span className="tabular-nums whitespace-nowrap max-sm:hidden">Host {variant} ({VARIANTS[index]!.name})</span>
      <span className="font-semibold sm:hidden" title={VARIANTS[index]!.name}>{variant}</span>
      <button type="button" aria-label="Next variant" className={btn} onClick={() => step(1)}>→</button>
      <span className="h-4 w-px bg-current opacity-30 max-sm:h-px max-sm:w-4" />
      {DATASETS.map((d) => (
        <button key={d} type="button" aria-pressed={d === dataset} className={cn(btn, d === dataset && "bg-white/20 font-semibold dark:bg-black/15")} onClick={() => setParam("state", d)}>
          <span className="max-sm:hidden">{d}</span>
          <span className="sm:hidden">{d[0]}</span>
        </button>
      ))}
    </div>,
    document.body,
  );
}
