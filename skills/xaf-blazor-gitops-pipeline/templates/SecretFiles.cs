using Microsoft.Extensions.Configuration.KeyPerFile;
using Microsoft.Extensions.FileProviders;

namespace {{APP_PROJECT}}.Hosting;

public static class SecretFiles {
    public const string DefaultDirectory = "/run/secrets";

    public static IConfigurationBuilder AddSecretFiles(this IConfigurationBuilder builder, string directory) {
        var source = new SecretFilesConfigurationSource { DirectoryPath = directory, Optional = true };
        if(Directory.Exists(directory)) {
            source.FileProvider = new PhysicalFileProvider(directory);
        }
        return builder.Add(source);
    }

    public static IHostBuilder UseSecretFiles(this IHostBuilder hostBuilder, string directory) {
        return hostBuilder.ConfigureAppConfiguration((_, configuration) => configuration.AddSecretFiles(directory));
    }
}

public class SecretFilesConfigurationSource : KeyPerFileConfigurationSource {
    public string DirectoryPath { get; init; }
}
