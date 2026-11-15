# Host load prototype (throwaway)

Three variants (A core cells, B thread bars, C expandable rows) of the thread details "Host" section,
built as a `/prototype` UI prototype against T3 nightly 0.1.10-nightly.20261115.4749.
Tim picked **A**. Copy `ThreadDetailsHost.prototype.tsx` into `apps/web/src/components/chat/` and apply
`ThreadDetailsPanel.mount.diff` to see the switcher again (`?variant=A|B|C`, `?state=devbox|mac`).
Not part of main; the validated decision lives in `patches-tt/0014`.
