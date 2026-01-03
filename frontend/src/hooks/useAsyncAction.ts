import { useCallback, useState } from "react";

type AsyncActionState<TArgs extends unknown[], TResult> = {
  pending: boolean;
  error: unknown | null;
  run: (...args: TArgs) => Promise<TResult | undefined>;
};

export function useAsyncAction<TArgs extends unknown[], TResult>(
  action: (...args: TArgs) => Promise<TResult>,
): AsyncActionState<TArgs, TResult> {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown | null>(null);

  const run = useCallback(
    async (...args: TArgs) => {
      setPending(true);
      setError(null);
      try {
        return await action(...args);
      } catch (err) {
        setError(err);
        return undefined;
      } finally {
        setPending(false);
      }
    },
    [action],
  );

  return { pending, error, run };
}
