import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def test_connection():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    with open("mongodb_connection_log.txt", "w") as log_file:
        try:
            # The ismaster command is cheap and does not require auth.
k            await client.admin.command('ismaster')
            log_file.write("Successfully connected to MongoDB\n")
            
            # Try to insert a document
            db = client.test_database
            result = await db.test_collection.insert_one({"test": "document"})
            log_file.write(f"Inserted document with id: {result.inserted_id}\n")
            
            # Try to find the document
            document = await db.test_collection.find_one({"test": "document"})
            if document:
                log_file.write(f"Found document: {document}\n")
            else:
                log_file.write("Document not found\n")
            
        except Exception as e:
            log_file.write(f"Failed to connect to MongoDB: {e}\n")
        finally:
            client.close()

if __name__ == "__main__":
    asyncio.run(test_connection())
    print("Connection test completed. Check mongodb_connection_log.txt for results.")