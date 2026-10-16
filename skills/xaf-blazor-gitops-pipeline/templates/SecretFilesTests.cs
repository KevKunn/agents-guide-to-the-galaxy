using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Hosting;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using {{APP_PROJECT}}.Hosting;

namespace {{TEST_PROJECT}}
{
	[TestClass]
	public class SecretFilesTests
	{
		private const string FileName = "ConnectionStrings__ConnectionString";
		private const string Key = "ConnectionStrings:ConnectionString";
		private const string EnvironmentPrefix = "SECRETFILESTEST_";

		private string _directory;

		[TestInitialize]
		public void CreateDirectory()
		{
			_directory = Path.Combine(Path.GetTempPath(), "secrets-" + Guid.NewGuid().ToString("N"));
			Directory.CreateDirectory(_directory);
		}

		[TestCleanup]
		public void DeleteDirectory()
		{
			Directory.Delete(_directory, recursive: true);
		}

		[TestMethod]
		public void FileName_DoubleUnderscore_MapsToColonKey()
		{
			WriteSecret(FileName, "from-file");

			var configuration = new ConfigurationBuilder().AddSecretFiles(_directory).Build();

			Assert.AreEqual("from-file", configuration[Key]);
			Assert.AreEqual("from-file", configuration.GetConnectionString("ConnectionString"));
		}

		[TestMethod]
		public void SecretFile_OverridesInMemoryValue()
		{
			WriteSecret(FileName, "from-file");

			var configuration = new ConfigurationBuilder()
				.AddInMemoryCollection(new Dictionary<string, string> { [Key] = "from-memory" })
				.AddSecretFiles(_directory)
				.Build();

			Assert.AreEqual("from-file", configuration[Key]);
		}

		[TestMethod]
		public void SecretFile_OverridesEnvironmentVariable()
		{
			WriteSecret(FileName, "from-file");
			var variable = EnvironmentPrefix + FileName;
			Environment.SetEnvironmentVariable(variable, "from-environment");
			try
			{
				var configuration = new ConfigurationBuilder()
					.AddEnvironmentVariables(EnvironmentPrefix)
					.AddSecretFiles(_directory)
					.Build();

				Assert.AreEqual("from-file", configuration[Key]);
			}
			finally
			{
				Environment.SetEnvironmentVariable(variable, null);
			}
		}

		[TestMethod]
		public void TrailingPlatformNewLine_IsRemoved()
		{
			WriteSecret(FileName, "from-file" + Environment.NewLine);

			var configuration = new ConfigurationBuilder().AddSecretFiles(_directory).Build();

			Assert.AreEqual("from-file", configuration[Key]);
		}

		[TestMethod]
		public void TrailingLineFeed_IsRemovedOnlyWhereItIsThePlatformNewLine()
		{
			WriteSecret(FileName, "from-file\n");

			var configuration = new ConfigurationBuilder().AddSecretFiles(_directory).Build();

			Assert.AreEqual(Environment.NewLine == "\n" ? "from-file" : "from-file\n", configuration[Key]);
		}

		[TestMethod]
		public void MissingDirectory_IsIgnored()
		{
			var missing = Path.Combine(_directory, "missing");

			var configuration = new ConfigurationBuilder()
				.AddInMemoryCollection(new Dictionary<string, string> { [Key] = "from-memory" })
				.AddSecretFiles(missing)
				.Build();

			Assert.AreEqual("from-memory", configuration[Key]);
		}

		[TestMethod]
		public void HostBuilder_SecretFiles_OverrideCommandLine()
		{
			WriteSecret(FileName, "from-file");

			using var host = Host.CreateDefaultBuilder(new[] { "--" + Key + "=from-command-line" })
				.UseSecretFiles(_directory)
				.Build();
			var configuration = (IConfigurationRoot)host.Services.GetService(typeof(IConfiguration));

			Assert.AreEqual("from-file", configuration[Key]);
			Assert.IsInstanceOfType(configuration.Providers.Last(), typeof(Microsoft.Extensions.Configuration.KeyPerFile.KeyPerFileConfigurationProvider));
		}

		[TestMethod]
		public void ProgramHostBuilder_AddsRunSecretsAsLastSource()
		{
			List<IConfigurationSource> sources = null;
			var hostBuilder = {{APP_PROJECT}}.Program.CreateHostBuilder(new[] { "--SecretFilesTest=1" })
				.ConfigureAppConfiguration((_, configuration) => sources = configuration.Sources.ToList());
			try
			{
				hostBuilder.Build().Dispose();
			}
			catch (Exception)
			{
				// Start-up checks may throw without a connection string.
			}

			Assert.IsNotNull(sources);
			var last = sources.Last() as Microsoft.Extensions.Configuration.KeyPerFile.KeyPerFileConfigurationSource;
			Assert.IsNotNull(last, "last source: " + sources.Last().GetType().Name);
			Assert.IsTrue(last.Optional);
			Assert.AreEqual(SecretFiles.DefaultDirectory, ((SecretFilesConfigurationSource)last).DirectoryPath);
			Assert.AreEqual("/run/secrets", SecretFiles.DefaultDirectory);
			var commandLine = sources.FindLastIndex(source => source is Microsoft.Extensions.Configuration.CommandLine.CommandLineConfigurationSource);
			var environment = sources.FindLastIndex(source => source is Microsoft.Extensions.Configuration.EnvironmentVariables.EnvironmentVariablesConfigurationSource);
			Assert.IsTrue(commandLine >= 0 && commandLine < sources.Count - 1);
			Assert.IsTrue(environment >= 0 && environment < sources.Count - 1);
		}

		private void WriteSecret(string name, string value)
		{
			File.WriteAllText(Path.Combine(_directory, name), value);
		}
	}
}
