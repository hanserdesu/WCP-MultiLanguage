using System.Runtime.CompilerServices;

// Keep the mechanism types internal to the plugin while allowing the
// out-of-game regression executable to exercise the same compiled assembly.
[assembly: InternalsVisibleTo("RegistryTest")]
