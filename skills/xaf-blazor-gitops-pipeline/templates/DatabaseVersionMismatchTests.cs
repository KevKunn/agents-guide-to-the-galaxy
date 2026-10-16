using System.Collections.Generic;
using System.Reflection;
using DevExpress.ExpressApp;
using DevExpress.ExpressApp.Updating;
using DevExpress.ExpressApp.Xpo;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using {{APP_PROJECT}};

namespace {{TEST_PROJECT}}
{
	[TestClass]
	public class DatabaseVersionMismatchTests
	{
		[TestMethod]
		public void Constructor_ChecksDatabaseSchema()
		{
			using var application = new {{APPLICATION_CLASS}}();

			Assert.AreEqual(CheckCompatibilityType.DatabaseSchema, application.CheckCompatibilityType);
		}

		[TestMethod]
		public void Mismatch_RunsUpdaterAndMarksHandled()
		{
			using var application = new {{APPLICATION_CLASS}}();
			var updater = new RecordingUpdater();
			var args = new DatabaseVersionMismatchEventArgs(updater, null);

			application.{{APPLICATION_CLASS}}_DatabaseVersionMismatch(application, args);

			Assert.AreEqual(1, updater.UpdateCalls);
			Assert.IsTrue(args.Handled);
		}

		[TestMethod]
		public void RaisedMismatch_ReachesTheHandler()
		{
			using var application = new {{APPLICATION_CLASS}}();
			var updater = new RecordingUpdater();
			var args = new DatabaseVersionMismatchEventArgs(updater, null);
			var raise = typeof(XafApplication).GetMethod("OnDatabaseVersionMismatch", BindingFlags.Instance | BindingFlags.NonPublic);

			raise.Invoke(application, new object[] { args });

			Assert.AreEqual(1, updater.UpdateCalls);
			Assert.IsTrue(args.Handled);
		}

		private sealed class RecordingUpdater : DatabaseUpdater
		{
			public RecordingUpdater() : base(new XPObjectSpaceProvider(new MemoryDataStoreProvider(), false), new List<ModuleBase>(), "{{TEST_PROJECT}}", null)
			{
			}

			public int UpdateCalls { get; private set; }

			public override void Update()
			{
				UpdateCalls++;
			}
		}
	}
}
