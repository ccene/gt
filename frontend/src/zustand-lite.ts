import { useSyncExternalStore } from "react";

type Listener = () => void;

export type SetState<T> = (partial: Partial<T> | ((s: T) => Partial<T>)) => void;

export interface StoreHook<T extends object> {
  (): T;
  <U>(selector: (s: T) => U): U;
  getState: () => T;
}

type AnyFn = (...args: never[]) => unknown;

export function create<T extends object>(initializer: (set: SetState<T>) => T): StoreHook<T> {
  let state: T;
  const listeners = new Set<Listener>();
  const set = (partial: Partial<T> | ((s: T) => Partial<T>)) => {
    const next = typeof partial === "function" ? partial(state) : partial;
    state = { ...state, ...next };
    listeners.forEach((l) => l());
  };
  state = initializer(set);
  const subscribe = (l: Listener) => {
    listeners.add(l);
    return () => listeners.delete(l);
  };
  const getSnapshot = () => state;
  function useStore(): T;
  function useStore<U>(selector: (s: T) => U): U;
  function useStore<U>(selector?: (s: T) => U): T | U {
    const snapshot = useSyncExternalStore(subscribe, getSnapshot);
    return selector ? selector(snapshot) : snapshot;
  }
  useStore.getState = () => state;
  return useStore;
}
