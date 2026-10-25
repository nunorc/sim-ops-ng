export default function getEnv(name: string, default_?: string): string | undefined {
  const _name = `VITE_${name}`
  if (_name in import.meta.env)
    return import.meta.env?.[_name] as string

  return default_
}

